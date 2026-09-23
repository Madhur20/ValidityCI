from __future__ import annotations

import json
import unittest

from validityci.checks.entity_overlap import run_entity_overlap_check
from validityci.schemas import (
    CheckResult,
    CheckStatus,
    ExecutionResult,
    ExecutionStatus,
    ExperimentConfig,
    RuntimeDataFingerprint,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeTrace,
)


class EntityOverlapCheckTests(unittest.TestCase):
    def test_overlap_is_a_blocking_failure_without_entity_values(self) -> None:
        check, evidence, findings = run_entity_overlap_check(
            self._config(), (self._execution(overlap_count=2, test_count=4),)
        )

        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(findings[0].severity, "blocking")
        self.assertEqual(findings[0].confidence, "high")
        self.assertEqual(findings[0].policy_id, "policy.entity_overlap_confirmed")
        self.assertEqual(findings[0].policy_version, "1.0.0")
        details = evidence[0].to_dict()["details"]
        self.assertEqual(details["splits"][0]["overlap_count"], 2)
        self.assertEqual(details["splits"][0]["test_overlap_rate"], 0.5)
        serialized = json.dumps(details)
        self.assertNotIn("entity_values", serialized)
        self.assertNotIn("entity_hashes", serialized)

    def test_disjoint_entities_pass_with_evidence(self) -> None:
        check, evidence, findings = run_entity_overlap_check(
            self._config(), (self._execution(overlap_count=0, test_count=4),)
        )

        self.assertEqual(check.status, CheckStatus.PASS)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(findings, ())

    def test_missing_entity_column_is_not_applicable(self) -> None:
        config = ExperimentConfig(
            task_type="binary_classification",
            target_column="target",
            primary_metric="accuracy",
        )

        check, evidence, findings = run_entity_overlap_check(
            config, (self._execution(overlap_count=0, test_count=4),)
        )

        self.assertEqual(check.status, CheckStatus.NOT_APPLICABLE)
        self.assertEqual(evidence, ())
        self.assertEqual(findings, ())

    def test_missing_split_measurement_is_unsupported(self) -> None:
        execution = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:output",
            runtime_trace=RuntimeTrace(
                fingerprint_scope_id="scope.1234", events=()
            ),
        )

        check, evidence, findings = run_entity_overlap_check(
            self._config(), (execution,)
        )

        self.assertEqual(check.status, CheckStatus.UNSUPPORTED)
        self.assertEqual(evidence, ())
        self.assertEqual(findings, ())

    def test_partial_measurement_cannot_be_reported_as_pass(self) -> None:
        measured_execution = self._execution(overlap_count=0, test_count=4)
        measured_event = measured_execution.runtime_trace.events[0]  # type: ignore[union-attr]
        unsupported_event = RuntimeEvent(
            id="runtime.2",
            sequence=2,
            event_type=RuntimeEventType.SPLIT,
            operation="sklearn.model_selection.train_test_split",
            cell_index=3,
            inputs=measured_event.inputs,
            parameters={
                "entity_overlap": {
                    "status": "unsupported",
                    "reason": "The entity series was not passed to this split",
                }
            },
        )
        execution = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:output",
            runtime_trace=RuntimeTrace(
                fingerprint_scope_id="scope.1234",
                events=(measured_event, unsupported_event),
            ),
        )

        check, evidence, findings = run_entity_overlap_check(
            self._config(), (execution,)
        )

        self.assertEqual(check.status, CheckStatus.UNSUPPORTED)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(findings, ())

    def test_overlap_in_repeated_execution_is_not_ignored(self) -> None:
        executions = (
            self._execution(
                overlap_count=0,
                test_count=4,
                execution_id="execution.original",
            ),
            self._execution(
                overlap_count=1,
                test_count=4,
                execution_id="execution.repeated",
            ),
        )

        check, evidence, findings = run_entity_overlap_check(
            self._config(), executions
        )

        self.assertEqual(check.status, CheckStatus.FAIL)
        self.assertEqual(len(evidence[0].details["splits"]), 2)
        self.assertEqual(len(findings), 1)

    def test_cross_validation_folds_are_evaluated_independently(self) -> None:
        execution = self._cross_validation_execution((0, 1))

        check, evidence, findings = run_entity_overlap_check(
            self._config(), (execution,)
        )

        self.assertEqual(check.status, CheckStatus.FAIL)
        splits = evidence[0].details["splits"]
        self.assertEqual(
            [(item["split_kind"], item["fold_index"]) for item in splits],
            [("cross_validation", 1), ("cross_validation", 2)],
        )
        self.assertEqual(findings[0].policy_id, "policy.entity_overlap_confirmed")

    def test_check_result_round_trips(self) -> None:
        original = CheckResult(
            check_id="split.entity_overlap",
            status=CheckStatus.PASS,
            summary="No overlap was observed.",
            evidence_ids=("evidence.entity_overlap",),
        )

        restored = CheckResult.from_dict(json.loads(json.dumps(original.to_dict())))

        self.assertEqual(restored, original)

    @staticmethod
    def _config() -> ExperimentConfig:
        return ExperimentConfig(
            task_type="binary_classification",
            target_column="target",
            primary_metric="accuracy",
            entity_column="entity_id",
        )

    @staticmethod
    def _execution(
        *,
        overlap_count: int,
        test_count: int,
        execution_id: str = "execution.original",
    ) -> ExecutionResult:
        fingerprint = RuntimeDataFingerprint(
            role="input.0",
            fingerprint="hmac-sha256:data",
            data_type="dataframe",
            row_count=10,
            column_count=2,
        )
        event = RuntimeEvent(
            id="runtime.1",
            sequence=1,
            event_type=RuntimeEventType.SPLIT,
            operation="sklearn.model_selection.train_test_split",
            cell_index=2,
            inputs=(fingerprint,),
            parameters={
                "entity_overlap": {
                    "status": "measured",
                    "train_unique_count": 8,
                    "test_unique_count": test_count,
                    "overlap_count": overlap_count,
                    "test_overlap_rate": overlap_count / test_count,
                }
            },
        )
        return ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:output",
            runtime_trace=RuntimeTrace(
                fingerprint_scope_id=f"scope.{execution_id}", events=(event,)
            ),
        )

    @staticmethod
    def _cross_validation_execution(
        overlap_counts: tuple[int, ...],
    ) -> ExecutionResult:
        fingerprint = RuntimeDataFingerprint(
            role="input.0",
            fingerprint="hmac-sha256:data",
            data_type="dataframe",
            row_count=10,
            column_count=2,
        )
        events = tuple(
            RuntimeEvent(
                id=f"runtime.{index}",
                sequence=index,
                event_type=RuntimeEventType.SPLIT,
                operation="sklearn.model_selection._split.GroupKFold.split",
                cell_index=2,
                inputs=(fingerprint,),
                parameters={
                    "split_kind": "cross_validation",
                    "fold_index": index,
                    "entity_overlap": {
                        "status": "measured",
                        "train_unique_count": 5,
                        "test_unique_count": 5,
                        "overlap_count": overlap_count,
                        "test_overlap_rate": overlap_count / 5,
                    },
                },
            )
            for index, overlap_count in enumerate(overlap_counts, start=1)
        )
        return ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:output",
            runtime_trace=RuntimeTrace(
                fingerprint_scope_id="scope.execution.original", events=events
            ),
        )


if __name__ == "__main__":
    unittest.main()
