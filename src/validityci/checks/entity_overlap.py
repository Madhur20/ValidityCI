from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from validityci.schemas import (
    CheckResult,
    CheckStatus,
    Confidence,
    Evidence,
    ExecutionResult,
    ExecutionStatus,
    ExperimentConfig,
    Finding,
    RuntimeEventType,
    Severity,
)


CHECK_ID = "split.entity_overlap"


def run_entity_overlap_check(
    config: ExperimentConfig,
    executions: tuple[ExecutionResult, ...],
) -> tuple[CheckResult, tuple[Evidence, ...], tuple[Finding, ...]]:
    if config.entity_column is None:
        return (
            CheckResult(
                check_id=CHECK_ID,
                status=CheckStatus.NOT_APPLICABLE,
                summary="No entity column was configured for this experiment.",
            ),
            (),
            (),
        )
    if not executions:
        return _unsupported("No execution was available for entity-overlap analysis.")
    if any(
        execution.status is not ExecutionStatus.SUCCEEDED
        for execution in executions
    ):
        return (
            CheckResult(
                check_id=CHECK_ID,
                status=CheckStatus.ERROR,
                summary="Entity overlap could not run because execution did not succeed.",
            ),
            (),
            (),
        )
    measurements: list[dict[str, Any]] = []
    unsupported_reasons: list[str] = []
    for execution in executions:
        if execution.runtime_trace is None:
            unsupported_reasons.append(
                f"{execution.execution_id} did not contain a runtime trace."
            )
            continue
        split_events = tuple(
            event
            for event in execution.runtime_trace.events
            if event.event_type is RuntimeEventType.SPLIT
        )
        if not split_events:
            unsupported_reasons.append(
                f"{execution.execution_id} contained no supported train/test split."
            )
            continue
        for event in split_events:
            raw = event.parameters.get("entity_overlap")
            if not isinstance(raw, Mapping):
                unsupported_reasons.append(
                    f"{execution.execution_id}/{event.id} did not contain "
                    "entity-overlap instrumentation."
                )
                continue
            status = raw.get("status")
            if status == "measured":
                try:
                    train_count = _non_negative_int(raw, "train_unique_count")
                    test_count = _non_negative_int(raw, "test_unique_count")
                    overlap_count = _non_negative_int(raw, "overlap_count")
                    overlap_rate = _rate(raw, "test_overlap_rate")
                except (TypeError, ValueError) as error:
                    return (
                        CheckResult(
                            check_id=CHECK_ID,
                            status=CheckStatus.ERROR,
                            summary=f"Entity-overlap evidence was invalid: {error}",
                        ),
                        (),
                        (),
                    )
                if overlap_count > min(train_count, test_count):
                    return (
                        CheckResult(
                            check_id=CHECK_ID,
                            status=CheckStatus.ERROR,
                            summary="Entity-overlap counts were internally inconsistent.",
                        ),
                        (),
                        (),
                    )
                measurements.append(
                    {
                        "execution_id": execution.execution_id,
                        "runtime_event_id": event.id,
                        "cell_index": event.cell_index,
                        "train_unique_count": train_count,
                        "test_unique_count": test_count,
                        "overlap_count": overlap_count,
                        "test_overlap_rate": overlap_rate,
                    }
                )
            elif status == "error":
                reason = raw.get("reason")
                return (
                    CheckResult(
                        check_id=CHECK_ID,
                        status=CheckStatus.ERROR,
                        summary=(
                            str(reason)
                            if isinstance(reason, str) and reason.strip()
                            else "Entity-overlap instrumentation failed."
                        ),
                    ),
                    (),
                    (),
                )
            else:
                reason = raw.get("reason")
                unsupported_reasons.append(
                    str(reason)
                    if isinstance(reason, str) and reason.strip()
                    else (
                        f"{execution.execution_id}/{event.id} did not support "
                        "entity-overlap measurement."
                    )
                )

    if not measurements:
        return _unsupported(" ".join(dict.fromkeys(unsupported_reasons)))

    evidence = Evidence(
        id="evidence.entity_overlap",
        kind="runtime_entity_overlap",
        summary=(
            f"Measured entity overlap for {len(measurements)} supported split "
            f"event{'s' if len(measurements) != 1 else ''}."
        ),
        details={
            "entity_column": config.entity_column,
            "splits": measurements,
            "partially_unsupported": bool(unsupported_reasons),
        },
        notebook_cells=tuple(
            sorted({measurement["cell_index"] for measurement in measurements})
        ),
    )
    overlapping = [item for item in measurements if item["overlap_count"] > 0]
    if not overlapping and unsupported_reasons:
        return (
            CheckResult(
                check_id=CHECK_ID,
                status=CheckStatus.UNSUPPORTED,
                summary=(
                    "Some observed splits could not be checked for entity overlap: "
                    + " ".join(dict.fromkeys(unsupported_reasons))
                ),
                evidence_ids=(evidence.id,),
            ),
            (evidence,),
            (),
        )
    if not overlapping:
        return (
            CheckResult(
                check_id=CHECK_ID,
                status=CheckStatus.PASS,
                summary="No configured entities overlapped across supported splits.",
                evidence_ids=(evidence.id,),
            ),
            (evidence,),
            (),
        )

    maximum = max(overlapping, key=lambda item: item["test_overlap_rate"])
    finding = Finding(
        id="finding.entity_overlap",
        check_id=CHECK_ID,
        title="Entities overlap between training and test partitions",
        severity=Severity.BLOCKING,
        confidence=Confidence.HIGH,
        summary=(
            f"A supported split placed {maximum['overlap_count']} configured "
            f"entities in both training and test data "
            f"({maximum['test_overlap_rate']:.1%} of test entities)."
        ),
        evidence_ids=(evidence.id,),
        recommendation=(
            "Split by the configured entity so every entity belongs to only one "
            "partition, then retrain and reevaluate the model."
        ),
    )
    return (
        CheckResult(
            check_id=CHECK_ID,
            status=CheckStatus.FAIL,
            summary="Configured entities overlap across training and test data.",
            evidence_ids=(evidence.id,),
        ),
        (evidence,),
        (finding,),
    )


def _unsupported(
    reason: str,
) -> tuple[CheckResult, tuple[Evidence, ...], tuple[Finding, ...]]:
    return (
        CheckResult(
            check_id=CHECK_ID,
            status=CheckStatus.UNSUPPORTED,
            summary=reason or "Entity overlap could not be measured.",
        ),
        (),
        (),
    )


def _non_negative_int(raw: Mapping[str, Any], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer")
    if value < 0:
        raise ValueError(f"{key} cannot be negative")
    return value


def _rate(raw: Mapping[str, Any], key: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be numeric")
    rate = float(value)
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"{key} must be between zero and one")
    return rate
