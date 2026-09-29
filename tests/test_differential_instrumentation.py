from __future__ import annotations

import unittest

from validityci.differential import compare_instrumented_and_reference
from validityci.schemas import (
    ExecutionFailure,
    ExecutionResult,
    ExecutionStatus,
    RuntimeTrace,
)


class DifferentialInstrumentationTests(unittest.TestCase):
    def test_matching_user_outputs_are_equivalent(self) -> None:
        instrumented = self._success(
            "execution.instrumented", "sha256:same", instrumented=True
        )
        reference = self._success(
            "execution.reference", "sha256:same", instrumented=False
        )

        result = compare_instrumented_and_reference(instrumented, reference)

        self.assertTrue(result.equivalent)
        self.assertTrue(result.status_match)
        self.assertTrue(result.output_match)
        self.assertIsNone(result.failure_match)
        self.assertEqual(result.reasons, ())

    def test_changed_user_output_fails_comparison(self) -> None:
        instrumented = self._success(
            "execution.instrumented", "sha256:first", instrumented=True
        )
        reference = self._success(
            "execution.reference", "sha256:second", instrumented=False
        )

        result = compare_instrumented_and_reference(instrumented, reference)

        self.assertFalse(result.equivalent)
        self.assertFalse(result.output_match)
        self.assertIn("Normalized user outputs differed", result.reasons)

    def test_matching_original_cell_failure_is_equivalent(self) -> None:
        failure = ExecutionFailure(
            kind="notebook_cell_error",
            message="NameError: missing_name",
            cell_index=2,
        )
        instrumented = ExecutionResult(
            execution_id="execution.instrumented",
            status=ExecutionStatus.CELL_FAILED,
            duration_ms=8,
            failure=failure,
        )
        reference = ExecutionResult(
            execution_id="execution.reference",
            status=ExecutionStatus.CELL_FAILED,
            duration_ms=3,
            failure=failure,
        )

        result = compare_instrumented_and_reference(instrumented, reference)

        self.assertTrue(result.equivalent)
        self.assertTrue(result.failure_match)
        self.assertIsNone(result.output_match)

    def test_reference_instrumentation_is_rejected(self) -> None:
        instrumented = self._success(
            "execution.instrumented", "sha256:same", instrumented=True
        )
        reference = self._success(
            "execution.reference", "sha256:same", instrumented=True
        )

        result = compare_instrumented_and_reference(instrumented, reference)

        self.assertFalse(result.equivalent)
        self.assertIn(
            "Reference execution unexpectedly produced instrumentation",
            result.reasons,
        )

    def test_matching_runner_errors_do_not_establish_equivalence(self) -> None:
        failure = ExecutionFailure(
            kind="container_error",
            message="Docker API unavailable",
        )
        instrumented = ExecutionResult(
            execution_id="execution.instrumented",
            status=ExecutionStatus.RUNNER_ERROR,
            duration_ms=4,
            failure=failure,
        )
        reference = ExecutionResult(
            execution_id="execution.reference",
            status=ExecutionStatus.RUNNER_ERROR,
            duration_ms=4,
            failure=failure,
        )

        result = compare_instrumented_and_reference(instrumented, reference)

        self.assertFalse(result.equivalent)
        self.assertIn("Only successful execution", result.reasons[0])

    @staticmethod
    def _success(
        execution_id: str, fingerprint: str, *, instrumented: bool
    ) -> ExecutionResult:
        return ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.SUCCEEDED,
            duration_ms=5,
            output_fingerprint=fingerprint,
            runtime_trace=(
                RuntimeTrace(fingerprint_scope_id="scope.test", events=())
                if instrumented
                else None
            ),
        )


if __name__ == "__main__":
    unittest.main()
