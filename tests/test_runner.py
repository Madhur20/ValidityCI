from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validityci.audit import audit_experiment
from validityci.runner import FakeRunner, Runner
from validityci.reporting import write_html
from validityci.schemas import (
    AuditStatus,
    ExecutionFailure,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    MetricArtifact,
    MetricCaptureMethod,
    MetricCaptureStatus,
    MetricSelector,
    ResourceLimits,
    RuntimeDataFingerprint,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeTrace,
)


class ExecutionSchemaTests(unittest.TestCase):
    def test_request_and_result_round_trip_through_json(self) -> None:
        request = ExecutionRequest(
            execution_id="execution.original",
            notebook_path="/workspace/experiment.ipynb",
            data_paths=("/workspace/data.csv",),
            working_directory="/workspace",
            metric_selector=MetricSelector(
                metric_name="accuracy", variable_name="accuracy"
            ),
            entity_column="customer_id",
        )
        result = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=125,
            output_fingerprint="sha256:abc123",
            metrics=(self._captured_metric(),),
        )

        restored_request = ExecutionRequest.from_dict(
            json.loads(json.dumps(request.to_dict()))
        )
        restored_result = ExecutionResult.from_dict(
            json.loads(json.dumps(result.to_dict()))
        )

        self.assertEqual(restored_request, request)
        self.assertEqual(restored_request.entity_column, "customer_id")
        self.assertEqual(restored_result, result)

    def test_unsupported_metric_round_trips_without_a_value(self) -> None:
        artifact = MetricArtifact(
            id="metric.1",
            metric_name="accuracy",
            status=MetricCaptureStatus.UNSUPPORTED,
            capture_method=MetricCaptureMethod.NOT_OBSERVED,
            reason="No supported runtime call was observed",
        )

        restored = MetricArtifact.from_dict(
            json.loads(json.dumps(artifact.to_dict()))
        )

        self.assertEqual(restored, artifact)
        self.assertIsNone(restored.value)

    def test_captured_metric_rejects_non_finite_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            MetricArtifact(
                id="metric.1",
                metric_name="accuracy",
                status=MetricCaptureStatus.CAPTURED,
                capture_method=MetricCaptureMethod.RUNTIME_WRAPPER,
                value=float("nan"),
            )

    def test_success_requires_fingerprint(self) -> None:
        with self.assertRaisesRegex(ValueError, "output_fingerprint"):
            ExecutionResult(
                execution_id="execution.original",
                status=ExecutionStatus.SUCCEEDED,
                duration_ms=1,
            )

    def test_failure_requires_details(self) -> None:
        with self.assertRaisesRegex(ValueError, "failure details"):
            ExecutionResult(
                execution_id="execution.original",
                status=ExecutionStatus.TIMED_OUT,
                duration_ms=300_000,
            )

    def test_limits_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeout_seconds must be positive"):
            ResourceLimits(timeout_seconds=0)

    @staticmethod
    def _captured_metric() -> MetricArtifact:
        return MetricArtifact(
            id="metric.1",
            metric_name="accuracy",
            status=MetricCaptureStatus.CAPTURED,
            capture_method=MetricCaptureMethod.RUNTIME_WRAPPER,
            value=0.9,
            cell_index=1,
            sample_count=10,
        )


class FakeRunnerTests(unittest.TestCase):
    def test_satisfies_runner_protocol_and_records_requests(self) -> None:
        result = self._success("execution.original", "sha256:first")
        runner = FakeRunner([result])
        request = self._request("execution.original")

        returned = runner.execute(request)

        self.assertIsInstance(runner, Runner)
        self.assertEqual(returned, result)
        self.assertEqual(runner.requests, (request,))

    def test_rejects_a_result_for_another_execution(self) -> None:
        runner = FakeRunner([self._success("execution.other", "sha256:first")])

        with self.assertRaisesRegex(ValueError, "does not match"):
            runner.execute(self._request("execution.original"))

    def test_raises_when_no_result_remains(self) -> None:
        runner = FakeRunner([])

        with self.assertRaisesRegex(RuntimeError, "no result configured"):
            runner.execute(self._request("execution.original"))

    def test_can_model_non_deterministic_outputs(self) -> None:
        runner = FakeRunner(
            [
                self._success("execution.first", "sha256:first"),
                self._success("execution.second", "sha256:second"),
            ]
        )

        first = runner.execute(self._request("execution.first"))
        second = runner.execute(self._request("execution.second"))

        self.assertNotEqual(first.output_fingerprint, second.output_fingerprint)

    @staticmethod
    def _request(execution_id: str) -> ExecutionRequest:
        return ExecutionRequest(
            execution_id=execution_id,
            notebook_path="/workspace/experiment.ipynb",
            data_paths=("/workspace/data.csv",),
            working_directory="/workspace",
        )

    @staticmethod
    def _success(execution_id: str, fingerprint: str) -> ExecutionResult:
        return ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint=fingerprint,
        )


class RunnerOrchestrationTests(unittest.TestCase):
    def test_successful_execution_is_attached_to_report(self) -> None:
        result = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:stable",
            metrics=(ExecutionSchemaTests._captured_metric(),),
            runtime_trace=self._clean_entity_trace(),
        )
        runner = FakeRunner([result])

        report = self._audit(runner)

        self.assertEqual(report.executions, (result,))
        self.assertEqual(report.status, AuditStatus.ATTENTION_REQUIRED)
        self.assertFalse(runner.requests[0].network_enabled)
        self.assertEqual(runner.requests[0].limits, ResourceLimits())
        self.assertEqual(
            runner.requests[0].metric_selector,
            MetricSelector(metric_name="accuracy", variable_name="accuracy"),
        )

    def test_cell_failure_makes_report_incomplete(self) -> None:
        runner = FakeRunner(
            [
                ExecutionResult(
                    execution_id="execution.original",
                    status=ExecutionStatus.CELL_FAILED,
                    duration_ms=25,
                    failure=ExecutionFailure(
                        kind="notebook_cell_error",
                        message="NameError: model is not defined",
                        cell_index=4,
                    ),
                )
            ]
        )

        report = self._audit(runner)

        self.assertEqual(report.status, AuditStatus.INCOMPLETE)
        self.assertEqual(report.executions[0].failure.cell_index, 4)  # type: ignore[union-attr]

    def test_timeout_makes_report_incomplete(self) -> None:
        runner = FakeRunner(
            [
                ExecutionResult(
                    execution_id="execution.original",
                    status=ExecutionStatus.TIMED_OUT,
                    duration_ms=1_000,
                    failure=ExecutionFailure(
                        kind="execution_timeout",
                        message="Execution exceeded 1 second",
                    ),
                )
            ]
        )

        report = self._audit(runner, limits=ResourceLimits(timeout_seconds=1))

        self.assertEqual(report.status, AuditStatus.INCOMPLETE)
        self.assertEqual(runner.requests[0].limits.timeout_seconds, 1)

    def test_unsupported_primary_metric_makes_report_incomplete(self) -> None:
        result = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:stable",
            metrics=(
                MetricArtifact(
                    id="metric.1",
                    metric_name="accuracy",
                    status=MetricCaptureStatus.UNSUPPORTED,
                    capture_method=MetricCaptureMethod.NOT_OBSERVED,
                    reason="No supported runtime call was observed",
                ),
            ),
        )

        report = self._audit(FakeRunner([result]))

        self.assertEqual(report.status, AuditStatus.INCOMPLETE)

    def test_entity_overlap_adds_blocking_finding(self) -> None:
        result = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:stable",
            metrics=(ExecutionSchemaTests._captured_metric(),),
            runtime_trace=self._clean_entity_trace(overlap_count=2),
        )

        report = self._audit(FakeRunner([result]))

        self.assertEqual(report.status, AuditStatus.ATTENTION_REQUIRED)
        self.assertEqual(report.checks[0].status, "fail")
        overlap_finding = next(
            finding
            for finding in report.findings
            if finding.check_id == "split.entity_overlap"
        )
        self.assertEqual(overlap_finding.severity, "blocking")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "audit.html"
            write_html(report, output)
            rendered = output.read_text(encoding="utf-8")
        self.assertIn("Deterministic checks", rendered)
        self.assertIn("split.entity_overlap", rendered)
        self.assertIn("FAIL", rendered)

    def test_preprocessing_leakage_adds_blocking_finding(self) -> None:
        result = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:stable",
            metrics=(ExecutionSchemaTests._captured_metric(),),
            runtime_trace=self._preprocessing_leak_trace(),
        )

        report = self._audit(FakeRunner([result]))

        self.assertEqual(report.status, AuditStatus.ATTENTION_REQUIRED)
        preprocessing_check = next(
            check
            for check in report.checks
            if check.check_id == "preprocessing.fit_scope"
        )
        self.assertEqual(preprocessing_check.status, "fail")
        preprocessing_finding = next(
            finding
            for finding in report.findings
            if finding.check_id == "preprocessing.fit_scope"
        )
        self.assertEqual(preprocessing_finding.severity, "blocking")

    def test_execution_failure_is_visible_in_html_report(self) -> None:
        runner = FakeRunner(
            [
                ExecutionResult(
                    execution_id="execution.original",
                    status=ExecutionStatus.CELL_FAILED,
                    duration_ms=25,
                    failure=ExecutionFailure(
                        kind="notebook_cell_error",
                        message="NameError: model is not defined",
                        cell_index=4,
                    ),
                )
            ]
        )
        report = self._audit(runner)

        with TemporaryDirectory() as directory:
            output = Path(directory) / "audit.html"
            write_html(report, output)
            rendered = output.read_text(encoding="utf-8")

        self.assertIn("Execution", rendered)
        self.assertIn("cell failed", rendered)
        self.assertIn("cell 4", rendered)
        self.assertIn("NameError: model is not defined", rendered)

    def test_captured_metric_is_visible_in_html_report(self) -> None:
        result = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:stable",
            metrics=(ExecutionSchemaTests._captured_metric(),),
        )
        report = self._audit(FakeRunner([result]))

        self.assertEqual(report.status, AuditStatus.INCOMPLETE)

        with TemporaryDirectory() as directory:
            output = Path(directory) / "audit.html"
            write_html(report, output)
            rendered = output.read_text(encoding="utf-8")

        self.assertIn("accuracy", rendered)
        self.assertIn("0.9", rendered)
        self.assertIn("10 samples", rendered)

    @staticmethod
    def _audit(
        runner: FakeRunner, *, limits: ResourceLimits | None = None
    ):
        root = Path(__file__).parents[1]
        return audit_experiment(
            root / "examples" / "imbalanced_churn.ipynb",
            root / "examples" / "customer_churn.csv",
            root / "examples" / "validityci.toml",
            runner=runner,
            limits=limits,
        )

    @staticmethod
    def _clean_entity_trace(*, overlap_count: int = 0) -> RuntimeTrace:
        data = RuntimeDataFingerprint(
            role="input.0",
            fingerprint="hmac-sha256:data",
            data_type="dataframe",
            row_count=20,
            column_count=3,
        )
        return RuntimeTrace(
            fingerprint_scope_id="scope.test",
            events=(
                RuntimeEvent(
                    id="runtime.1",
                    sequence=1,
                    event_type=RuntimeEventType.SPLIT,
                    operation="sklearn.model_selection.train_test_split",
                    cell_index=1,
                    inputs=(data,),
                    parameters={
                        "entity_overlap": {
                            "status": "measured",
                            "train_unique_count": 15,
                            "test_unique_count": 5,
                            "overlap_count": overlap_count,
                            "test_overlap_rate": overlap_count / 5,
                        }
                    },
                ),
            ),
        )

    @staticmethod
    def _preprocessing_leak_trace() -> RuntimeTrace:
        full = RuntimeDataFingerprint(
            role="input.0",
            fingerprint="hmac-sha256:full",
            data_type="dataframe",
            row_count=20,
            column_count=3,
        )
        train = RuntimeDataFingerprint(
            role="output.0",
            fingerprint="hmac-sha256:train",
            data_type="dataframe",
            row_count=15,
            column_count=3,
        )
        test = RuntimeDataFingerprint(
            role="output.1",
            fingerprint="hmac-sha256:test",
            data_type="dataframe",
            row_count=5,
            column_count=3,
        )
        return RuntimeTrace(
            fingerprint_scope_id="scope.test",
            events=(
                RuntimeEvent(
                    id="runtime.1",
                    sequence=1,
                    event_type=RuntimeEventType.SPLIT,
                    operation="sklearn.model_selection.train_test_split",
                    cell_index=1,
                    inputs=(full,),
                    outputs=(train, test),
                    parameters={
                        "entity_overlap": {
                            "status": "measured",
                            "train_unique_count": 15,
                            "test_unique_count": 5,
                            "overlap_count": 0,
                            "test_overlap_rate": 0.0,
                        }
                    },
                ),
                RuntimeEvent(
                    id="runtime.2",
                    sequence=2,
                    event_type=RuntimeEventType.FIT,
                    operation="sklearn.preprocessing.StandardScaler.fit",
                    cell_index=2,
                    inputs=(test,),
                    parameters={"object_kind": "transformer"},
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
