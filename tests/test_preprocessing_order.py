from __future__ import annotations

import json
import unittest

from validityci.checks.preprocessing_order import run_preprocessing_order_check
from validityci.schemas import (
    CheckStatus,
    ExecutionResult,
    ExecutionStatus,
    RuntimeDataFingerprint,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeTrace,
)


class PreprocessingOrderCheckTests(unittest.TestCase):
    def test_training_only_fit_passes(self) -> None:
        check, evidence, findings = run_preprocessing_order_check(
            (self._execution("train"),)
        )

        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(
            evidence[0].details["observations"][0]["outcome"],
            "fit_on_train_data",
        )
        self.assertEqual(findings, ())

    def test_fit_before_split_is_blocking(self) -> None:
        check, evidence, findings = run_preprocessing_order_check(
            (self._execution("before"),)
        )

        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(findings[0].severity, "blocking")
        self.assertEqual(findings[0].confidence, "high")
        self.assertEqual(
            evidence[0].details["observations"][0]["outcome"],
            "fit_before_split",
        )

    def test_fit_on_full_data_is_blocking(self) -> None:
        check, evidence, findings = run_preprocessing_order_check(
            (self._execution("full"),)
        )

        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(
            evidence[0].details["observations"][0]["outcome"],
            "fit_on_full_data",
        )
        self.assertEqual(len(findings), 1)

    def test_fit_on_test_data_is_blocking(self) -> None:
        check, evidence, findings = run_preprocessing_order_check(
            (self._execution("test"),)
        )

        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(
            evidence[0].details["observations"][0]["outcome"],
            "fit_on_test_data",
        )
        self.assertEqual(len(findings), 1)

    def test_unknown_fit_lineage_requires_review(self) -> None:
        check, evidence, findings = run_preprocessing_order_check(
            (self._execution("unknown"),)
        )

        self.assertEqual(check.status, CheckStatus.REVIEW)
        self.assertEqual(findings[0].severity, "warning")
        self.assertEqual(findings[0].confidence, "medium")
        self.assertEqual(
            evidence[0].details["observations"][0]["outcome"],
            "unverified_fit_scope",
        )

    def test_estimator_fit_without_transformer_is_not_applicable(self) -> None:
        check, evidence, findings = run_preprocessing_order_check(
            (self._execution("estimator"),)
        )

        self.assertEqual(check.status, CheckStatus.NOT_APPLICABLE)
        self.assertEqual(evidence, ())
        self.assertEqual(findings, ())

    def test_trace_without_fit_or_split_is_not_applicable(self) -> None:
        execution = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:output",
            runtime_trace=RuntimeTrace(
                fingerprint_scope_id="scope.execution.original",
                events=(
                    RuntimeEvent(
                        id="runtime.1",
                        sequence=1,
                        event_type=RuntimeEventType.METRIC,
                        operation="sklearn.metrics.accuracy_score",
                        cell_index=1,
                        inputs=(self._data("metric", 20),),
                    ),
                ),
            ),
        )

        check, evidence, findings = run_preprocessing_order_check((execution,))

        self.assertEqual(check.status, CheckStatus.NOT_APPLICABLE)
        self.assertEqual(evidence, ())
        self.assertEqual(findings, ())

    def test_missing_object_kind_is_unsupported(self) -> None:
        check, evidence, findings = run_preprocessing_order_check(
            (self._execution("missing_kind"),)
        )

        self.assertEqual(check.status, CheckStatus.UNSUPPORTED)
        self.assertEqual(evidence, ())
        self.assertEqual(findings, ())

    def test_repeated_run_violation_is_not_ignored(self) -> None:
        executions = (
            self._execution("train", execution_id="execution.original"),
            self._execution("test", execution_id="execution.repeated"),
        )

        check, evidence, findings = run_preprocessing_order_check(executions)

        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(len(evidence[0].details["observations"]), 2)
        self.assertEqual(len(findings), 1)

    def test_evidence_contains_no_data_values(self) -> None:
        _, evidence, _ = run_preprocessing_order_check((self._execution("full"),))

        serialized = json.dumps(evidence[0].to_dict())
        self.assertNotIn("raw_data", serialized)
        self.assertNotIn("data_values", serialized)

    @classmethod
    def _execution(
        cls,
        scenario: str,
        *,
        execution_id: str = "execution.original",
    ) -> ExecutionResult:
        full = cls._data("full", 20)
        train = cls._data("train", 15)
        test = cls._data("test", 5)
        split = RuntimeEvent(
            id="runtime.1" if scenario != "before" else "runtime.2",
            sequence=1 if scenario != "before" else 2,
            event_type=RuntimeEventType.SPLIT,
            operation="sklearn.model_selection.train_test_split",
            cell_index=2,
            inputs=(full,),
            outputs=(train, test),
        )
        selected = {
            "train": train,
            "full": full,
            "test": test,
            "unknown": cls._data("derived", 15),
            "before": full,
            "estimator": train,
            "missing_kind": train,
        }[scenario]
        parameters = (
            {}
            if scenario == "missing_kind"
            else {
                "object_kind": (
                    "estimator" if scenario == "estimator" else "transformer"
                )
            }
        )
        fit = RuntimeEvent(
            id="runtime.2" if scenario != "before" else "runtime.1",
            sequence=2 if scenario != "before" else 1,
            event_type=RuntimeEventType.FIT,
            operation=(
                "sklearn.linear_model.LogisticRegression.fit"
                if scenario == "estimator"
                else "sklearn.preprocessing.StandardScaler.fit"
            ),
            cell_index=3 if scenario != "before" else 1,
            inputs=(selected,),
            parameters=parameters,
        )
        events = (fit, split) if scenario == "before" else (split, fit)
        return ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:output",
            runtime_trace=RuntimeTrace(
                fingerprint_scope_id=f"scope.{execution_id}", events=events
            ),
        )

    @staticmethod
    def _data(name: str, rows: int) -> RuntimeDataFingerprint:
        return RuntimeDataFingerprint(
            role="input.0",
            fingerprint=f"hmac-sha256:{name}",
            data_type="dataframe",
            row_count=rows,
            column_count=2,
        )


if __name__ == "__main__":
    unittest.main()
