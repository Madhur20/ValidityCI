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


if __name__ == "__main__":
    unittest.main()
