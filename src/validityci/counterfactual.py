"""Comparison for the controlled group-isolated split counterfactual."""

from __future__ import annotations

from collections.abc import Mapping

from validityci.schemas import (
    CounterfactualComparison,
    CounterfactualStatus,
    ExecutionResult,
    ExecutionStatus,
    ExecutionVariant,
    MetricCaptureStatus,
    RuntimeEventType,
)


def compare_group_isolated_counterfactual(
    baseline: ExecutionResult,
    counterfactual: ExecutionResult,
    primary_metric: str,
) -> CounterfactualComparison:
    transformation_count = _transformation_count(counterfactual)
    baseline_values = _captured_values(baseline, primary_metric)
    counterfactual_values = _captured_values(counterfactual, primary_metric)
    reasons: list[str] = []
    if baseline.execution_variant is not ExecutionVariant.OBSERVED:
        reasons.append("The baseline execution was not the observed experiment")
    if (
        counterfactual.execution_variant
        is not ExecutionVariant.GROUP_ISOLATED_COUNTERFACTUAL
    ):
        reasons.append("The comparison execution was not a group-isolated variant")
    if baseline.status is not ExecutionStatus.SUCCEEDED:
        reasons.append(f"Baseline execution ended with {baseline.status.value}")
    if counterfactual.status is not ExecutionStatus.SUCCEEDED:
        reasons.append(
            f"Counterfactual execution ended with {counterfactual.status.value}"
        )
    if transformation_count < 1:
        reasons.append("No supported train/test split was transformed")
    if len(baseline_values) != 1:
        reasons.append("Baseline must contain exactly one captured primary metric")
    if len(counterfactual_values) != 1:
        reasons.append(
            "Counterfactual must contain exactly one captured primary metric"
        )

    baseline_value = baseline_values[0] if len(baseline_values) == 1 else None
    counterfactual_value = (
        counterfactual_values[0] if len(counterfactual_values) == 1 else None
    )
    if reasons:
        return CounterfactualComparison(
            status=CounterfactualStatus.INCOMPLETE,
            baseline_execution_id=baseline.execution_id,
            counterfactual_execution_id=counterfactual.execution_id,
            primary_metric=primary_metric,
            transformation_count=transformation_count,
            baseline_metric_value=baseline_value,
            counterfactual_metric_value=counterfactual_value,
            reason="; ".join(dict.fromkeys(reasons)),
        )
    assert baseline_value is not None
    assert counterfactual_value is not None
    return CounterfactualComparison(
        status=CounterfactualStatus.COMPARED,
        baseline_execution_id=baseline.execution_id,
        counterfactual_execution_id=counterfactual.execution_id,
        primary_metric=primary_metric,
        transformation_count=transformation_count,
        baseline_metric_value=baseline_value,
        counterfactual_metric_value=counterfactual_value,
        metric_delta=counterfactual_value - baseline_value,
    )


def _transformation_count(execution: ExecutionResult) -> int:
    if execution.runtime_trace is None:
        return 0
    count = 0
    for event in execution.runtime_trace.events:
        if event.event_type is not RuntimeEventType.SPLIT:
            continue
        raw = event.parameters.get("counterfactual")
        if isinstance(raw, Mapping) and raw.get("status") == "applied":
            count += 1
    return count


def _captured_values(
    execution: ExecutionResult, metric_name: str
) -> tuple[float, ...]:
    return tuple(
        metric.value
        for metric in execution.metrics
        if metric.metric_name == metric_name
        and metric.status is MetricCaptureStatus.CAPTURED
        and metric.value is not None
    )


__all__ = ["compare_group_isolated_counterfactual"]
