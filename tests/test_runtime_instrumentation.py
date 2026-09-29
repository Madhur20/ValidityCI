from __future__ import annotations

import json
import unittest

from validityci.schemas import (
    ExecutionResult,
    ExecutionStatus,
    INSTRUMENTATION_SCHEMA_VERSION,
    RuntimeDataFingerprint,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeTrace,
)


class RuntimeInstrumentationSchemaTests(unittest.TestCase):
    def test_versioned_trace_round_trips_with_ordered_events(self) -> None:
        trace = RuntimeTrace(
            fingerprint_scope_id="scope.1234",
            events=(
                RuntimeEvent(
                    id="runtime.1",
                    sequence=1,
                    event_type=RuntimeEventType.SPLIT,
                    operation="sklearn.model_selection.train_test_split",
                    cell_index=2,
                    inputs=(self._fingerprint("input.0", 20, 3),),
                    outputs=(
                        self._fingerprint("output.0", 16, 3),
                        self._fingerprint("output.1", 4, 3),
                    ),
                    parameters={"test_size": 0.2, "random_state": 42},
                ),
                RuntimeEvent(
                    id="runtime.2",
                    sequence=2,
                    event_type=RuntimeEventType.FIT,
                    operation="sklearn.linear_model.LogisticRegression.fit",
                    cell_index=3,
                    inputs=(self._fingerprint("input.0", 16, 3),),
                ),
            ),
        )
        result = ExecutionResult(
            execution_id="execution.original",
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=10,
            output_fingerprint="sha256:output",
            runtime_trace=trace,
        )

        restored = ExecutionResult.from_dict(json.loads(json.dumps(result.to_dict())))

        self.assertEqual(restored, result)
        self.assertEqual(trace.schema_version, INSTRUMENTATION_SCHEMA_VERSION)
        serialized = trace.to_dict()
        self.assertNotIn("raw_data", json.dumps(serialized))
        self.assertNotIn("fingerprint_key", json.dumps(serialized))

    def test_trace_rejects_unordered_sequences(self) -> None:
        event = RuntimeEvent(
            id="runtime.2",
            sequence=2,
            event_type=RuntimeEventType.PREDICT,
            operation="sklearn.linear_model.LogisticRegression.predict",
            cell_index=4,
            inputs=(self._fingerprint("input.0", 4, 3),),
        )

        with self.assertRaisesRegex(ValueError, "contiguous and ordered"):
            RuntimeTrace(fingerprint_scope_id="scope.1234", events=(event,))

    def test_trace_rejects_unknown_instrumentation_version(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "Unsupported instrumentation schema version"
        ):
            RuntimeTrace(
                fingerprint_scope_id="scope.1234",
                events=(),
                schema_version="99.0.0",
            )

    def test_event_requires_a_data_fingerprint(self) -> None:
        with self.assertRaisesRegex(ValueError, "data fingerprint"):
            RuntimeEvent(
                id="runtime.1",
                sequence=1,
                event_type=RuntimeEventType.FIT,
                operation="example.Estimator.fit",
                cell_index=0,
            )

    def test_cross_validation_fold_round_trips_without_row_indices(self) -> None:
        event = RuntimeEvent(
            id="runtime.1",
            sequence=1,
            event_type=RuntimeEventType.SPLIT,
            operation="sklearn.model_selection._split.GroupKFold.split",
            cell_index=1,
            inputs=(self._fingerprint("input.0", 20, 2),),
            outputs=(
                self._fingerprint("output.0", 10, 2),
                self._fingerprint("output.1", 10, 2),
            ),
            parameters={
                "split_kind": "cross_validation",
                "fold_index": 1,
                "parallel_execution": False,
            },
        )

        restored = RuntimeEvent.from_dict(
            json.loads(json.dumps(event.to_dict()))
        )

        self.assertEqual(restored, event)
        serialized = json.dumps(restored.to_dict())
        self.assertNotIn("train_indices", serialized)
        self.assertNotIn("test_indices", serialized)

    def test_iterable_cross_validation_adapter_round_trips_without_indices(self) -> None:
        event = RuntimeEvent(
            id="runtime.1",
            sequence=1,
            event_type=RuntimeEventType.SPLIT,
            operation="sklearn.model_selection._split._CVIterableWrapper.split",
            cell_index=1,
            inputs=(self._fingerprint("input.0", 20, 2),),
            outputs=(
                self._fingerprint("output.0", 10, 2),
                self._fingerprint("output.1", 10, 2),
            ),
            parameters={
                "split_kind": "cross_validation",
                "cv_adapter": "iterable",
                "fold_index": 1,
                "parallel_execution": False,
            },
        )

        restored = RuntimeEvent.from_dict(json.loads(json.dumps(event.to_dict())))

        self.assertEqual(restored.parameters["cv_adapter"], "iterable")
        serialized = json.dumps(restored.to_dict())
        self.assertNotIn("train_indices", serialized)
        self.assertNotIn("test_indices", serialized)

    @staticmethod
    def _fingerprint(
        role: str, rows: int, columns: int | None
    ) -> RuntimeDataFingerprint:
        return RuntimeDataFingerprint(
            role=role,
            fingerprint=f"hmac-sha256:{role}",
            data_type="dataframe" if columns is not None else "series",
            row_count=rows,
            column_count=columns,
        )


if __name__ == "__main__":
    unittest.main()
