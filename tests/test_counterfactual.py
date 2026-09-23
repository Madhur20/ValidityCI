from __future__ import annotations

import json
import unittest

from validityci.counterfactual import compare_group_isolated_counterfactual
from validityci.schemas import (
    CounterfactualComparison,
    CounterfactualStatus,
    ExecutionResult,
    ExecutionStatus,
    ExecutionVariant,
    MetricArtifact,
    MetricCaptureMethod,
    MetricCaptureStatus,
    RuntimeDataFingerprint,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeTrace,
)


class CounterfactualComparisonTests(unittest.TestCase):
    def test_compares_one_metric_after_a_supported_transformation(self) -> None:
        baseline = self._execution("execution.original", 0.9)
        counterfactual = self._execution(
            "execution.counterfactual.group_isolated",
            0.7,
            variant=ExecutionVariant.GROUP_ISOLATED_COUNTERFACTUAL,
            transformed=True,
        )

        comparison = compare_group_isolated_counterfactual(
            baseline, counterfactual, "accuracy"
        )
        restored = CounterfactualComparison.from_dict(
            json.loads(json.dumps(comparison.to_dict()))
        )

        self.assertEqual(restored, comparison)
        self.assertEqual(comparison.status, CounterfactualStatus.COMPARED)
        self.assertEqual(comparison.transformation_count, 1)
        self.assertAlmostEqual(comparison.metric_delta, -0.2)

    def test_no_transformed_split_is_incomplete(self) -> None:
        comparison = compare_group_isolated_counterfactual(
            self._execution("execution.original", 0.9),
            self._execution(
                "execution.counterfactual.group_isolated",
                0.8,
                variant=ExecutionVariant.GROUP_ISOLATED_COUNTERFACTUAL,
            ),
            "accuracy",
        )

        self.assertEqual(comparison.status, CounterfactualStatus.INCOMPLETE)
        self.assertIn("No supported train/test split", comparison.reason or "")
        self.assertIsNone(comparison.metric_delta)

    def test_multiple_metric_calls_are_not_collapsed(self) -> None:
        counterfactual = self._execution(
            "execution.counterfactual.group_isolated",
            0.8,
            variant=ExecutionVariant.GROUP_ISOLATED_COUNTERFACTUAL,
            transformed=True,
            extra_metric=0.7,
        )

        comparison = compare_group_isolated_counterfactual(
            self._execution("execution.original", 0.9),
            counterfactual,
            "accuracy",
        )

        self.assertEqual(comparison.status, CounterfactualStatus.INCOMPLETE)
        self.assertIn("exactly one captured", comparison.reason or "")

    def test_schema_rejects_a_delta_that_does_not_match_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "metric_delta"):
            CounterfactualComparison(
                status=CounterfactualStatus.COMPARED,
                baseline_execution_id="execution.original",
                counterfactual_execution_id="execution.counterfactual",
                primary_metric="accuracy",
                transformation_count=1,
                baseline_metric_value=0.9,
                counterfactual_metric_value=0.8,
                metric_delta=0.1,
            )

    @staticmethod
    def _execution(
        execution_id: str,
        metric_value: float,
        *,
        variant: ExecutionVariant = ExecutionVariant.OBSERVED,
        transformed: bool = False,
        extra_metric: float | None = None,
    ) -> ExecutionResult:
        values = (metric_value,) if extra_metric is None else (metric_value, extra_metric)
        metrics = tuple(
            MetricArtifact(
                id=f"metric.{index}",
                metric_name="accuracy",
                status=MetricCaptureStatus.CAPTURED,
                capture_method=MetricCaptureMethod.RUNTIME_WRAPPER,
                value=value,
                cell_index=1,
                sample_count=4,
            )
            for index, value in enumerate(values, start=1)
        )
        data = RuntimeDataFingerprint(
            role="input.0",
            fingerprint="hmac-sha256:data",
            data_type="dataframe",
            row_count=12,
            column_count=3,
        )
        trace = RuntimeTrace(
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
                        "counterfactual": {
                            "status": "applied" if transformed else "not_requested",
                            "kind": "group_isolated_split",
                        }
                    },
                ),
            ),
        )
        return ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint=f"sha256:{execution_id}",
            metrics=metrics,
            runtime_trace=trace,
            execution_variant=variant,
        )


if __name__ == "__main__":
    unittest.main()
