from __future__ import annotations

from typing import Any

from validityci.schemas import (
    CheckResult,
    CheckStatus,
    Confidence,
    Evidence,
    ExecutionResult,
    ExecutionStatus,
    Finding,
    RuntimeEvent,
    RuntimeEventType,
    Severity,
)


CHECK_ID = "preprocessing.fit_scope"


def run_preprocessing_order_check(
    executions: tuple[ExecutionResult, ...],
) -> tuple[CheckResult, tuple[Evidence, ...], tuple[Finding, ...]]:
    if not executions:
        return _unsupported("No execution was available for preprocessing analysis.")
    if any(
        execution.status is not ExecutionStatus.SUCCEEDED
        for execution in executions
    ):
        return (
            CheckResult(
                check_id=CHECK_ID,
                status=CheckStatus.ERROR,
                summary="Preprocessing order could not run because execution failed.",
            ),
            (),
            (),
        )

    observations: list[dict[str, Any]] = []
    unsupported_reasons: list[str] = []
    observed_transformer_fit = False
    for execution in executions:
        trace = execution.runtime_trace
        if trace is None:
            unsupported_reasons.append(
                f"{execution.execution_id} did not contain a runtime trace."
            )
            continue
        fit_candidates = tuple(
            event
            for event in trace.events
            if event.event_type is RuntimeEventType.FIT
            or (
                event.event_type is RuntimeEventType.TRANSFORM
                and event.operation.endswith(".fit_transform")
            )
        )
        missing_kind = tuple(
            event
            for event in fit_candidates
            if event.parameters.get("object_kind") not in {"transformer", "estimator"}
        )
        if missing_kind:
            unsupported_reasons.append(
                f"{execution.execution_id} contained fit events without object-kind metadata."
            )

        transformer_fits = tuple(
            event
            for event in fit_candidates
            if event.parameters.get("object_kind") == "transformer"
        )
        if not transformer_fits:
            continue
        observed_transformer_fit = observed_transformer_fit or bool(transformer_fits)
        split_events = tuple(
            event
            for event in trace.events
            if event.event_type is RuntimeEventType.SPLIT
        )
        if not split_events:
            unsupported_reasons.append(
                f"{execution.execution_id} contained no supported train/test split."
            )
            continue
        for fit_event in transformer_fits:
            observations.append(
                _classify_fit(execution.execution_id, fit_event, split_events)
            )

    violations = tuple(
        item
        for item in observations
        if item["outcome"] in {"fit_before_split", "fit_on_full_data", "fit_on_test_data"}
    )
    reviews = tuple(
        item for item in observations if item["outcome"] == "unverified_fit_scope"
    )
    if not observations:
        if unsupported_reasons:
            return _unsupported(" ".join(dict.fromkeys(unsupported_reasons)))
        if not observed_transformer_fit:
            return (
                CheckResult(
                    check_id=CHECK_ID,
                    status=CheckStatus.NOT_APPLICABLE,
                    summary="No supported transformer fitting was observed.",
                ),
                (),
                (),
            )

    evidence = Evidence(
        id="evidence.preprocessing_fit_scope",
        kind="runtime_preprocessing_fit_scope",
        summary=(
            f"Classified {len(observations)} supported transformer fit "
            f"event{'s' if len(observations) != 1 else ''}."
        ),
        details={
            "observations": observations,
            "partially_unsupported": bool(unsupported_reasons),
        },
        notebook_cells=tuple(
            sorted({item["cell_index"] for item in observations})
        ),
    )
    if violations:
        first = violations[0]
        reason = {
            "fit_before_split": "before a supported train/test split completed",
            "fit_on_full_data": "on the full pre-split dataset",
            "fit_on_test_data": "on the held-out test partition",
        }[first["outcome"]]
        finding = Finding(
            id="finding.preprocessing_fit_scope",
            check_id=CHECK_ID,
            title="Preprocessing was fitted outside the training partition",
            severity=Severity.BLOCKING,
            confidence=Confidence.HIGH,
            summary=f"{first['operation']} was fitted {reason}.",
            evidence_ids=(evidence.id,),
            recommendation=(
                "Create the train/test split first, fit every preprocessing step only "
                "on training data, and use the fitted transformer to transform test data."
            ),
        )
        return (
            CheckResult(
                check_id=CHECK_ID,
                status=CheckStatus.FAIL,
                summary="Runtime lineage confirmed preprocessing leakage.",
                evidence_ids=(evidence.id,),
            ),
            (evidence,),
            (finding,),
        )
    if reviews:
        finding = Finding(
            id="finding.preprocessing_fit_scope_review",
            check_id=CHECK_ID,
            title="Preprocessing fit scope could not be established",
            severity=Severity.WARNING,
            confidence=Confidence.MEDIUM,
            summary=(
                "A supported transformer fit was observed after splitting, but its "
                "input did not match a captured training, test, or full dataset."
            ),
            evidence_ids=(evidence.id,),
            recommendation=(
                "Inspect the referenced cells and make preprocessing lineage explicit. "
                "Fit transformers only from the captured training partition."
            ),
        )
        return (
            CheckResult(
                check_id=CHECK_ID,
                status=CheckStatus.REVIEW,
                summary="Transformer fit scope requires reviewer confirmation.",
                evidence_ids=(evidence.id,),
            ),
            (evidence,),
            (finding,),
        )
    if unsupported_reasons:
        return (
            CheckResult(
                check_id=CHECK_ID,
                status=CheckStatus.UNSUPPORTED,
                summary=(
                    "Some preprocessing lineage was unsupported: "
                    + " ".join(dict.fromkeys(unsupported_reasons))
                ),
                evidence_ids=(evidence.id,),
            ),
            (evidence,),
            (),
        )
    return (
        CheckResult(
            check_id=CHECK_ID,
            status=CheckStatus.PASS,
            summary="Supported transformers were fitted only on training data.",
            evidence_ids=(evidence.id,),
        ),
        (evidence,),
        (),
    )


def _classify_fit(
    execution_id: str,
    fit_event: RuntimeEvent,
    split_events: tuple[RuntimeEvent, ...],
) -> dict[str, Any]:
    prior_splits = tuple(
        event for event in split_events if event.sequence < fit_event.sequence
    )
    observation: dict[str, Any] = {
        "execution_id": execution_id,
        "runtime_event_id": fit_event.id,
        "cell_index": fit_event.cell_index,
        "operation": fit_event.operation,
    }
    if not prior_splits:
        return {**observation, "outcome": "fit_before_split", "split_event_id": None}

    input_fingerprints = {item.fingerprint for item in fit_event.inputs}
    for split_event in reversed(prior_splits):
        full_fingerprints = {
            item.fingerprint for item in split_event.inputs[:1]
        }
        train_fingerprints = {
            item.fingerprint for item in split_event.outputs[:1]
        }
        test_fingerprints = {
            item.fingerprint for item in split_event.outputs[1:2]
        }
        if input_fingerprints & test_fingerprints:
            outcome = "fit_on_test_data"
        elif input_fingerprints & full_fingerprints:
            outcome = "fit_on_full_data"
        elif input_fingerprints & train_fingerprints:
            outcome = "fit_on_train_data"
        else:
            continue
        return {
            **observation,
            "outcome": outcome,
            "split_event_id": split_event.id,
        }
    return {
        **observation,
        "outcome": "unverified_fit_scope",
        "split_event_id": prior_splits[-1].id,
    }


def _unsupported(
    reason: str,
) -> tuple[CheckResult, tuple[Evidence, ...], tuple[Finding, ...]]:
    return (
        CheckResult(
            check_id=CHECK_ID,
            status=CheckStatus.UNSUPPORTED,
            summary=reason or "Preprocessing fit scope could not be established.",
        ),
        (),
        (),
    )
