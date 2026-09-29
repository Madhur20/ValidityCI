"""Compare instrumented execution with an uninstrumented reference run."""

from __future__ import annotations

from dataclasses import dataclass

from validityci.schemas import ExecutionResult, ExecutionStatus, JsonObject


@dataclass(frozen=True, slots=True)
class DifferentialInstrumentationResult:
    equivalent: bool
    status_match: bool
    output_match: bool | None
    failure_match: bool | None
    reasons: tuple[str, ...]

    def to_dict(self) -> JsonObject:
        return {
            "equivalent": self.equivalent,
            "status_match": self.status_match,
            "output_match": self.output_match,
            "failure_match": self.failure_match,
            "reasons": list(self.reasons),
        }


def compare_instrumented_and_reference(
    instrumented: ExecutionResult,
    reference: ExecutionResult,
) -> DifferentialInstrumentationResult:
    """Compare externally observable behavior, excluding duration and evidence."""

    reasons: list[str] = []
    status_match = instrumented.status is reference.status
    if not status_match:
        reasons.append("Execution statuses differed")

    output_match: bool | None = None
    failure_match: bool | None = None
    if (
        instrumented.status is ExecutionStatus.SUCCEEDED
        and reference.status is ExecutionStatus.SUCCEEDED
    ):
        output_match = instrumented.output_fingerprint == reference.output_fingerprint
        if not output_match:
            reasons.append("Normalized user outputs differed")
        if instrumented.runtime_trace is None:
            reasons.append("Instrumented execution did not produce a runtime trace")
        if reference.runtime_trace is not None or reference.metrics:
            reasons.append("Reference execution unexpectedly produced instrumentation")
    elif status_match and instrumented.status is ExecutionStatus.CELL_FAILED:
        failure_match = _failure_signature(instrumented) == _failure_signature(reference)
        if not failure_match:
            reasons.append("Failure kind, message, or original cell index differed")
    elif status_match:
        reasons.append(
            "Only successful execution or a matching original-cell failure can "
            "establish behavioral equivalence"
        )

    return DifferentialInstrumentationResult(
        equivalent=not reasons,
        status_match=status_match,
        output_match=output_match,
        failure_match=failure_match,
        reasons=tuple(reasons),
    )


def _failure_signature(result: ExecutionResult) -> tuple[str, str, int | None] | None:
    if result.failure is None:
        return None
    return (
        result.failure.kind,
        result.failure.message,
        result.failure.cell_index,
    )


__all__ = [
    "DifferentialInstrumentationResult",
    "compare_instrumented_and_reference",
]
