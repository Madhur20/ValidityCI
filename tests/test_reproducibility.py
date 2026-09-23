from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from validityci.audit import audit_experiment
from validityci.reporting import write_html
from validityci.reproducibility import compare_executions
from validityci.runner import FakeRunner
from validityci.schemas import (
    AuditStatus,
    AuditReport,
    EnvironmentFingerprint,
    ExecutionFailure,
    ExecutionResult,
    ExecutionStatus,
    MetricArtifact,
    MetricCaptureMethod,
    MetricCaptureStatus,
    ReproducibilityComparison,
    ReproducibilityStatus,
    RuntimeDataFingerprint,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeTrace,
)


class ReproducibilityComparisonTests(unittest.TestCase):
    def test_matching_executions_are_reproduced_and_round_trip(self) -> None:
        baseline = self._success("execution.original", (0.9,))
        repeated = self._success("execution.repeated", (0.9,))

        comparison = compare_executions(baseline, repeated, "accuracy")
        restored = ReproducibilityComparison.from_dict(
            json.loads(json.dumps(comparison.to_dict()))
        )
        restored_execution = ExecutionResult.from_dict(
            json.loads(json.dumps(baseline.to_dict()))
        )

        self.assertEqual(comparison.status, ReproducibilityStatus.REPRODUCED)
        self.assertTrue(comparison.metric_match)
        self.assertTrue(comparison.output_match)
        self.assertTrue(comparison.environment_match)
        self.assertEqual(comparison.max_absolute_delta, 0.0)
        self.assertEqual(restored, comparison)
        self.assertEqual(restored_execution, baseline)

    def test_metric_change_beyond_tolerance_diverges(self) -> None:
        baseline = self._success("execution.original", (0.9,))
        repeated = self._success(
            "execution.repeated", (0.85,), output="sha256:changed"
        )

        comparison = compare_executions(baseline, repeated, "accuracy")

        self.assertEqual(comparison.status, ReproducibilityStatus.DIVERGED)
        self.assertFalse(comparison.metric_match)
        self.assertFalse(comparison.output_match)
        self.assertAlmostEqual(comparison.max_absolute_delta, 0.05)

    def test_small_metric_change_within_tolerance_matches(self) -> None:
        baseline = self._success("execution.original", (0.9,))
        repeated = self._success("execution.repeated", (0.9 + 5e-13,))

        comparison = compare_executions(baseline, repeated, "accuracy")

        self.assertEqual(comparison.status, ReproducibilityStatus.REPRODUCED)

    def test_changed_metric_call_count_diverges(self) -> None:
        baseline = self._success("execution.original", (0.8, 0.9))
        repeated = self._success("execution.repeated", (0.8,))

        comparison = compare_executions(baseline, repeated, "accuracy")

        self.assertEqual(comparison.status, ReproducibilityStatus.DIVERGED)
        self.assertFalse(comparison.metric_match)
        self.assertIn("number", " ".join(comparison.reasons))

    def test_missing_environment_is_incomplete(self) -> None:
        baseline = self._success("execution.original", (0.9,))
        repeated = self._success("execution.repeated", (0.9,), environment=False)

        comparison = compare_executions(baseline, repeated, "accuracy")

        self.assertEqual(comparison.status, ReproducibilityStatus.INCOMPLETE)
        self.assertIsNone(comparison.environment_match)

    def test_failed_execution_is_incomplete(self) -> None:
        baseline = self._success("execution.original", (0.9,))
        repeated = ExecutionResult(
            execution_id="execution.repeated",
            status=ExecutionStatus.TIMED_OUT,
            duration_ms=1_000,
            failure=ExecutionFailure(
                kind="execution_timeout", message="Execution timed out"
            ),
        )

        comparison = compare_executions(baseline, repeated, "accuracy")

        self.assertEqual(comparison.status, ReproducibilityStatus.INCOMPLETE)
        self.assertIn("timed_out", " ".join(comparison.reasons))

    @classmethod
    def _success(
        cls,
        execution_id: str,
        values: tuple[float, ...],
        *,
        output: str = "sha256:output",
        environment: bool = True,
    ) -> ExecutionResult:
        return ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint=output,
            metrics=tuple(
                MetricArtifact(
                    id=f"metric.{index}",
                    metric_name="accuracy",
                    status=MetricCaptureStatus.CAPTURED,
                    capture_method=MetricCaptureMethod.RUNTIME_WRAPPER,
                    value=value,
                    cell_index=1,
                    sample_count=20,
                )
                for index, value in enumerate(values, start=1)
            ),
            environment=cls._environment() if environment else None,
            runtime_trace=cls._clean_entity_trace(),
        )

    @staticmethod
    def _environment() -> EnvironmentFingerprint:
        return EnvironmentFingerprint(
            fingerprint="sha256:environment",
            python_version="3.11.11",
            python_implementation="CPython",
            operating_system="Linux",
            machine="aarch64",
            packages_fingerprint="sha256:packages",
            runner_fingerprint="sha256:runner",
        )

    @staticmethod
    def _clean_entity_trace() -> RuntimeTrace:
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
                            "overlap_count": 0,
                            "test_overlap_rate": 0.0,
                        }
                    },
                ),
            ),
        )


class RepeatedAuditTests(unittest.TestCase):
    def test_divergence_adds_evidence_and_finding(self) -> None:
        runner = FakeRunner(
            [
                ReproducibilityComparisonTests._success(
                    "execution.original", (0.9,)
                ),
                ReproducibilityComparisonTests._success(
                    "execution.repeated", (0.8,), output="sha256:changed"
                ),
            ]
        )
        root = Path(__file__).parents[1]

        report = audit_experiment(
            root / "examples" / "imbalanced_churn.ipynb",
            root / "examples" / "customer_churn.csv",
            root / "examples" / "validityci.toml",
            runner=runner,
            execution_count=2,
        )

        self.assertEqual(report.status, AuditStatus.ATTENTION_REQUIRED)
        self.assertEqual(report.reproducibility.status, ReproducibilityStatus.DIVERGED)  # type: ignore[union-attr]
        reproducibility_finding = next(
            finding
            for finding in report.findings
            if finding.check_id == "reproducibility.repeated_execution"
        )
        self.assertEqual(
            reproducibility_finding.policy_id,
            "policy.reproducibility_divergence",
        )
        self.assertEqual(
            [request.execution_id for request in runner.requests],
            ["execution.original", "execution.repeated"],
        )

        restored = AuditReport.from_dict(
            json.loads(json.dumps(report.to_dict()))
        )
        self.assertEqual(restored, report)

        with TemporaryDirectory() as directory:
            output = Path(directory) / "audit.html"
            write_html(report, output)
            rendered = output.read_text(encoding="utf-8")
        self.assertIn("Reproducibility", rendered)
        self.assertIn("DIVERGED", rendered)
        self.assertIn("Environment match: True", rendered)


if __name__ == "__main__":
    unittest.main()
