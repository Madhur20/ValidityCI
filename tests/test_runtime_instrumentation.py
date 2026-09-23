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
