from __future__ import annotations

import json
import unittest

from validityci.schemas import (
    BinaryConfusionMatrix,
    ConfusionMatrixStatus,
    MetricArtifact,
    MetricCaptureMethod,
    MetricCaptureStatus,
)


class BinaryConfusionMatrixTests(unittest.TestCase):
    def test_captured_matrix_round_trips_as_aggregate_counts(self) -> None:
        metric = MetricArtifact(
            id="metric.1",
            metric_name="accuracy",
            status=MetricCaptureStatus.CAPTURED,
            capture_method=MetricCaptureMethod.RUNTIME_WRAPPER,
            value=0.8,
            sample_count=10,
            confusion_matrix=BinaryConfusionMatrix(
                status=ConfusionMatrixStatus.CAPTURED,
                positive_class="1",
                true_negative=6,
                false_positive=1,
                false_negative=1,
                true_positive=2,
            ),
        )

        restored = MetricArtifact.from_dict(
            json.loads(json.dumps(metric.to_dict()))
        )

        self.assertEqual(restored, metric)
        self.assertEqual(
            sum(
                (
                    restored.confusion_matrix.true_negative,
                    restored.confusion_matrix.false_positive,
                    restored.confusion_matrix.false_negative,
                    restored.confusion_matrix.true_positive,
                )
            ),
            10,
        )
        serialized = json.dumps(metric.to_dict())
        self.assertNotIn("y_true", serialized)
        self.assertNotIn("y_pred", serialized)
        self.assertNotIn("predictions", serialized)

    def test_unsupported_matrix_preserves_reason_without_counts(self) -> None:
        matrix = BinaryConfusionMatrix(
            status=ConfusionMatrixStatus.UNSUPPORTED,
            positive_class="1",
            reason="Observed outputs were not binary class labels",
        )

        restored = BinaryConfusionMatrix.from_dict(matrix.to_dict())

        self.assertEqual(restored, matrix)
        self.assertIsNone(restored.true_positive)

    def test_captured_matrix_requires_all_non_negative_counts(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            BinaryConfusionMatrix(
                status=ConfusionMatrixStatus.CAPTURED,
                positive_class="1",
                true_negative=6,
                false_positive=-1,
                false_negative=1,
                true_positive=2,
            )

    def test_unsupported_matrix_rejects_counts(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot contain counts"):
            BinaryConfusionMatrix(
                status=ConfusionMatrixStatus.UNSUPPORTED,
                positive_class="1",
                true_positive=1,
                reason="unsupported",
            )

    def test_metric_rejects_matrix_with_wrong_sample_total(self) -> None:
        with self.assertRaisesRegex(ValueError, "sum to metric sample_count"):
            MetricArtifact(
                id="metric.1",
                metric_name="accuracy",
                status=MetricCaptureStatus.CAPTURED,
                capture_method=MetricCaptureMethod.RUNTIME_WRAPPER,
                value=0.8,
                sample_count=10,
                confusion_matrix=BinaryConfusionMatrix(
                    status=ConfusionMatrixStatus.CAPTURED,
                    positive_class="1",
                    true_negative=6,
                    false_positive=1,
                    false_negative=1,
                    true_positive=1,
                ),
            )


if __name__ == "__main__":
    unittest.main()
