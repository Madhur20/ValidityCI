"""Deterministic comparison of two independent execution results."""

from __future__ import annotations

import math

from validityci.schemas import (
    ExecutionResult,
    ExecutionStatus,
    MetricCaptureStatus,
    ReproducibilityComparison,
    ReproducibilityStatus,
)


DEFAULT_METRIC_ABSOLUTE_TOLERANCE = 1e-12


def compare_executions(
    baseline: ExecutionResult,
    repeated: ExecutionResult,
    primary_metric: str,
    *,
    metric_absolute_tolerance: float = DEFAULT_METRIC_ABSOLUTE_TOLERANCE,
) -> ReproducibilityComparison:
    if metric_absolute_tolerance < 0 or not math.isfinite(metric_absolute_tolerance):
        raise ValueError("metric_absolute_tolerance must be finite and non-negative")

    reasons: list[str] = []
    if baseline.status is not ExecutionStatus.SUCCEEDED:
        reasons.append(f"Baseline execution ended with {baseline.status.value}")
    if repeated.status is not ExecutionStatus.SUCCEEDED:
        reasons.append(f"Repeated execution ended with {repeated.status.value}")

    baseline_values = _captured_values(baseline, primary_metric)
    repeated_values = _captured_values(repeated, primary_metric)
    metric_match: bool | None
    max_delta: float | None = None
    if not baseline_values or not repeated_values:
        metric_match = None
        reasons.append("The primary metric was not captured in both executions")
    elif len(baseline_values) != len(repeated_values):
        metric_match = False
        reasons.append("The number of captured primary-metric calls changed")
        paired_deltas = [
            abs(first - second)
            for first, second in zip(baseline_values, repeated_values, strict=False)
        ]
        max_delta = max(paired_deltas, default=None)
    else:
        deltas = [
            abs(first - second)
            for first, second in zip(baseline_values, repeated_values, strict=True)
        ]
        max_delta = max(deltas, default=0.0)
        metric_match = all(
            math.isclose(first, second, rel_tol=0.0, abs_tol=metric_absolute_tolerance)
            for first, second in zip(
                baseline_values, repeated_values, strict=True
            )
        )
        if not metric_match:
            reasons.append(
                "The primary metric changed beyond the absolute tolerance "
                f"of {metric_absolute_tolerance:g}"
            )

    output_match = _compare_optional_fingerprints(
        baseline.output_fingerprint,
        repeated.output_fingerprint,
        "Output fingerprints were unavailable for both executions",
        "Normalized notebook outputs changed",
        reasons,
    )
    environment_match = _compare_optional_fingerprints(
        None if baseline.environment is None else baseline.environment.fingerprint,
        None if repeated.environment is None else repeated.environment.fingerprint,
        "Environment fingerprints were unavailable for both executions",
        "Execution environments changed",
        reasons,
    )

    signals = (metric_match, output_match, environment_match)
    if None in signals:
        status = ReproducibilityStatus.INCOMPLETE
    elif False in signals:
        status = ReproducibilityStatus.DIVERGED
    else:
        status = ReproducibilityStatus.REPRODUCED
        reasons.clear()

    return ReproducibilityComparison(
        status=status,
        baseline_execution_id=baseline.execution_id,
        repeated_execution_id=repeated.execution_id,
        primary_metric=primary_metric,
        baseline_metric_values=baseline_values,
        repeated_metric_values=repeated_values,
        metric_match=metric_match,
        output_match=output_match,
        environment_match=environment_match,
        max_absolute_delta=max_delta,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _captured_values(execution: ExecutionResult, metric_name: str) -> tuple[float, ...]:
    return tuple(
        metric.value
        for metric in execution.metrics
        if metric.metric_name == metric_name
        and metric.status is MetricCaptureStatus.CAPTURED
        and metric.value is not None
    )


def _compare_optional_fingerprints(
    baseline: str | None,
    repeated: str | None,
    unavailable_reason: str,
    mismatch_reason: str,
    reasons: list[str],
) -> bool | None:
    if baseline is None or repeated is None:
        reasons.append(unavailable_reason)
        return None
    matches = baseline == repeated
    if not matches:
        reasons.append(mismatch_reason)
    return matches


__all__ = ["DEFAULT_METRIC_ABSOLUTE_TOLERANCE", "compare_executions"]
