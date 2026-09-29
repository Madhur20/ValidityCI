"""Read-only investigator context and deterministic fallback summary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from validityci.policy import finding_policies
from validityci.schemas import (
    AuditReport,
    CheckStatus,
    ExecutionStatus,
    JsonObject,
    MetricCaptureStatus,
)


@dataclass(frozen=True, slots=True)
class InvestigatorObservation:
    id: str
    summary: str
    evidence_ids: tuple[str, ...]

    def to_dict(self) -> JsonObject:
        return {
            "id": self.id,
            "summary": self.summary,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class InvestigatorSummary:
    experiment_claim: str
    verified_observations: tuple[InvestigatorObservation, ...]
    unresolved_assumptions: tuple[str, ...]
    reviewer_questions: tuple[str, ...]
    recommended_next_action: str
    source: str = "deterministic_fallback"

    def to_dict(self) -> JsonObject:
        return {
            "source": self.source,
            "experiment_claim": self.experiment_claim,
            "verified_observations": [
                observation.to_dict() for observation in self.verified_observations
            ],
            "unresolved_assumptions": list(self.unresolved_assumptions),
            "reviewer_questions": list(self.reviewer_questions),
            "recommended_next_action": self.recommended_next_action,
        }


@dataclass(frozen=True, slots=True)
class InvestigatorRun:
    summary: InvestigatorSummary
    used_fallback: bool
    rejection_reason: str | None = None

    def to_dict(self) -> JsonObject:
        return {
            "used_fallback": self.used_fallback,
            "rejection_reason": self.rejection_reason,
            "summary": self.summary.to_dict(),
        }


class InvestigatorAdapter(Protocol):
    def generate(self, context: "ReadOnlyInvestigatorContext") -> Mapping[str, Any]: ...


class ReadOnlyInvestigatorContext:
    """Narrow, immutable retrieval surface over one completed audit report."""

    def __init__(self, report: AuditReport) -> None:
        if not isinstance(report, AuditReport):
            raise TypeError("report must be an AuditReport")
        self._report = report

    def get_experiment_specification(self) -> JsonObject:
        return self._report.config.to_dict()

    def get_dataset_profile(self) -> JsonObject:
        return self._report.dataset.to_dict()

    def get_notebook_cell(self, cell_index: int) -> JsonObject:
        for cell in self._report.notebook.cells:
            if cell.index == cell_index:
                return cell.to_dict()
        raise KeyError(cell_index)

    def list_check_results(self) -> list[JsonObject]:
        return [check.to_dict() for check in self._report.checks]

    def get_evidence(self, evidence_id: str) -> JsonObject:
        for evidence in self._report.evidence:
            if evidence.id == evidence_id:
                return evidence.to_dict()
        raise KeyError(evidence_id)

    def get_execution_summary(self, execution_id: str) -> JsonObject:
        for execution in self._report.executions:
            if execution.execution_id != execution_id:
                continue
            return {
                "execution_id": execution.execution_id,
                "execution_variant": execution.execution_variant.value,
                "status": execution.status.value,
                "duration_ms": execution.duration_ms,
                "output_fingerprint": execution.output_fingerprint,
                "failure": (
                    None if execution.failure is None else execution.failure.to_dict()
                ),
                "metric_ids": [metric.id for metric in execution.metrics],
                "environment_fingerprint": (
                    None
                    if execution.environment is None
                    else execution.environment.fingerprint
                ),
                "runtime_event_count": (
                    0
                    if execution.runtime_trace is None
                    else len(execution.runtime_trace.events)
                ),
            }
        raise KeyError(execution_id)

    def list_runtime_events(
        self, execution_id: str, *, cell_index: int | None = None
    ) -> list[JsonObject]:
        execution = self._execution(execution_id)
        if execution.runtime_trace is None:
            return []
        return [
            event.to_dict()
            for event in execution.runtime_trace.events
            if cell_index is None or event.cell_index == cell_index
        ]

    def get_metric(self, execution_id: str, metric_id: str) -> JsonObject:
        execution = self._execution(execution_id)
        for metric in execution.metrics:
            if metric.id == metric_id:
                return {
                    "record_id": f"{execution.execution_id}/{metric.id}",
                    "execution_id": execution.execution_id,
                    **metric.to_dict(),
                }
        raise KeyError(metric_id)

    def compare_executions(self) -> JsonObject | None:
        comparison = self._report.reproducibility
        return None if comparison is None else comparison.to_dict()

    def get_counterfactual_comparison(self) -> JsonObject | None:
        comparison = self._report.counterfactual
        return None if comparison is None else comparison.to_dict()

    def list_policy_requirements(self) -> list[JsonObject]:
        return [
            {
                "policy_id": policy.policy_id,
                "version": policy.version,
                "severity": policy.severity.value,
                "confidence": policy.confidence.value,
                "rationale": policy.rationale,
            }
            for policy in finding_policies()
        ]

    def supporting_record_ids(self) -> tuple[str, ...]:
        values = {
            *(evidence.id for evidence in self._report.evidence),
            *(check.check_id for check in self._report.checks),
            *(execution.execution_id for execution in self._report.executions),
            *(
                f"{execution.execution_id}/{metric.id}"
                for execution in self._report.executions
                for metric in execution.metrics
            ),
        }
        return tuple(sorted(values))

    def _execution(self, execution_id: str):
        for execution in self._report.executions:
            if execution.execution_id == execution_id:
                return execution
        raise KeyError(execution_id)


def build_deterministic_investigator_summary(
    report: AuditReport,
) -> InvestigatorSummary:
    context = ReadOnlyInvestigatorContext(report)
    observations: list[InvestigatorObservation] = []
    unresolved: list[str] = []
    questions: list[str] = []

    for finding in report.findings:
        observations.append(
            InvestigatorObservation(
                id=f"observation.{finding.id}",
                summary=finding.summary,
                evidence_ids=finding.evidence_ids,
            )
        )
        question = _finding_question(finding.check_id)
        if question is not None:
            questions.append(question)

    for check in report.checks:
        if check.status is CheckStatus.PASS:
            observations.append(
                InvestigatorObservation(
                    id=f"observation.{check.check_id}.pass",
                    summary=check.summary,
                    evidence_ids=check.evidence_ids,
                )
            )
        elif check.status in {CheckStatus.UNSUPPORTED, CheckStatus.ERROR}:
            unresolved.append(check.summary)
            questions.append(
                f"What additional evidence is needed to complete {check.check_id}?"
            )

    for execution in report.executions:
        for metric in execution.metrics:
            if metric.status is MetricCaptureStatus.UNSUPPORTED:
                record_id = f"{execution.execution_id}/{metric.id}"
                reason = metric.reason or "The metric value was not captured."
                observations.append(
                    InvestigatorObservation(
                        id=f"observation.{execution.execution_id}.{metric.id}.unsupported",
                        summary=(
                            f"{metric.metric_name!r} metric capture was unsupported: "
                            f"{reason}"
                        ),
                        evidence_ids=(record_id,),
                    )
                )
                unresolved.append(
                    f"The declared metric {metric.metric_name!r} remains unavailable."
                )
                questions.append(
                    f"How should {metric.metric_name!r} be captured from the experiment?"
                )
        if execution.status is not ExecutionStatus.SUCCEEDED:
            message = (
                execution.failure.message
                if execution.failure is not None
                else "Execution did not succeed."
            )
            observations.append(
                InvestigatorObservation(
                    id=f"observation.{execution.execution_id}.failure",
                    summary=message,
                    evidence_ids=(execution.execution_id,),
                )
            )
            unresolved.append(
                "Runtime conclusions depending on the failed execution remain unresolved."
            )

    if report.reproducibility is not None:
        reproduction_evidence = next(
            (
                evidence.id
                for evidence in report.evidence
                if evidence.kind == "reproducibility_comparison"
            ),
            None,
        )
        reproduction_support = (
            (reproduction_evidence,)
            if reproduction_evidence is not None
            else (
                report.reproducibility.baseline_execution_id,
                report.reproducibility.repeated_execution_id,
            )
        )
        observations.append(
            InvestigatorObservation(
                id="observation.reproducibility",
                summary=(
                    "Repeated observed executions were "
                    f"{report.reproducibility.status.value}."
                ),
                evidence_ids=reproduction_support,
            )
        )
    if report.counterfactual is not None:
        counterfactual_evidence = next(
            (
                evidence.id
                for evidence in report.evidence
                if evidence.kind == "group_isolated_counterfactual"
            ),
            None,
        )
        counterfactual_support = (
            (counterfactual_evidence,)
            if counterfactual_evidence is not None
            else (
                report.counterfactual.baseline_execution_id,
                report.counterfactual.counterfactual_execution_id,
            )
        )
        observations.append(
            InvestigatorObservation(
                id="observation.counterfactual",
                summary=(
                    "The group-isolated counterfactual was "
                    f"{report.counterfactual.status.value}."
                ),
                evidence_ids=counterfactual_support,
            )
        )

    if not observations:
        unresolved.append(
            "No deterministic finding or supported runtime check produced a reviewer observation."
        )
    questions.append(
        "Does the evaluated data and task match the intended deployment population and decision?"
    )
    recommended_next_action = _next_action(report)
    claim = (
        f"Evaluate a {report.config.task_type.replace('_', ' ')} experiment predicting "
        f"{report.config.target_column!r} with {report.config.primary_metric!r} as "
        "the declared primary metric."
    )
    known_ids = set(context.supporting_record_ids())
    for observation in observations:
        if not set(observation.evidence_ids).issubset(known_ids):
            unresolved.append(
                f"Supporting record for {observation.id} was not available in this report."
            )
    return InvestigatorSummary(
        experiment_claim=claim,
        verified_observations=tuple(observations),
        unresolved_assumptions=tuple(dict.fromkeys(unresolved)),
        reviewer_questions=tuple(dict.fromkeys(questions)),
        recommended_next_action=recommended_next_action,
    )


def run_investigator(
    report: AuditReport,
    adapter: InvestigatorAdapter | None = None,
) -> InvestigatorRun:
    fallback = build_deterministic_investigator_summary(report)
    if adapter is None:
        return InvestigatorRun(summary=fallback, used_fallback=True)
    context = ReadOnlyInvestigatorContext(report)
    try:
        draft = adapter.generate(context)
        summary = _validated_summary(draft, context)
    except Exception as error:
        return InvestigatorRun(
            summary=fallback,
            used_fallback=True,
            rejection_reason=f"{type(error).__name__}: {error}",
        )
    return InvestigatorRun(summary=summary, used_fallback=False)


def _validated_summary(
    raw: Mapping[str, Any], context: ReadOnlyInvestigatorContext
) -> InvestigatorSummary:
    if not isinstance(raw, Mapping):
        raise TypeError("Investigator output must be an object")
    expected = {
        "experiment_claim",
        "verified_observations",
        "unresolved_assumptions",
        "reviewer_questions",
        "recommended_next_action",
    }
    missing = sorted(expected - set(raw))
    unknown = sorted(set(raw) - expected)
    if missing:
        raise ValueError(f"Missing investigator output fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"Unknown investigator output fields: {', '.join(unknown)}")
    known_support = set(context.supporting_record_ids())
    observations_raw = raw["verified_observations"]
    if not isinstance(observations_raw, list):
        raise TypeError("verified_observations must be an array")
    observations: list[InvestigatorObservation] = []
    observation_ids: set[str] = set()
    for value in observations_raw:
        if not isinstance(value, Mapping):
            raise TypeError("Investigator observations must be objects")
        if set(value) != {"id", "summary", "evidence_ids"}:
            raise ValueError("Investigator observations have invalid fields")
        observation_id = _required_text(value["id"], "observation id")
        if observation_id in observation_ids:
            raise ValueError("Investigator observation IDs must be unique")
        observation_ids.add(observation_id)
        evidence_raw = value["evidence_ids"]
        if not isinstance(evidence_raw, list) or not evidence_raw:
            raise ValueError("Investigator observations require evidence IDs")
        evidence_ids = tuple(
            _required_text(item, "observation evidence ID") for item in evidence_raw
        )
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Observation evidence IDs must be unique")
        unknown_evidence = sorted(set(evidence_ids) - known_support)
        if unknown_evidence:
            raise ValueError(
                "Investigator observation references unknown evidence: "
                + ", ".join(unknown_evidence)
            )
        observations.append(
            InvestigatorObservation(
                id=observation_id,
                summary=_required_text(value["summary"], "observation summary"),
                evidence_ids=evidence_ids,
            )
        )
    return InvestigatorSummary(
        experiment_claim=_required_text(raw["experiment_claim"], "experiment claim"),
        verified_observations=tuple(observations),
        unresolved_assumptions=_text_array(
            raw["unresolved_assumptions"], "unresolved assumptions"
        ),
        reviewer_questions=_text_array(
            raw["reviewer_questions"], "reviewer questions"
        ),
        recommended_next_action=_required_text(
            raw["recommended_next_action"], "recommended next action"
        ),
        source="validated_adapter",
    )


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _text_array(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    normalized = tuple(_required_text(item, label) for item in value)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must be unique")
    return normalized


def _finding_question(check_id: str) -> str | None:
    return MappingProxyType(
        {
            "metric_suitability.class_imbalance": (
                "What are the relative costs of false positives and false negatives?"
            ),
            "split.entity_overlap": (
                "Does the configured entity represent the deployment isolation boundary?"
            ),
            "preprocessing.fit_scope": (
                "Can preprocessing be rerun using training data only?"
            ),
            "reproducibility.repeated_execution": (
                "Which randomness, ordering, parallelism, or external state remains uncontrolled?"
            ),
        }
    ).get(check_id)


def _next_action(report: AuditReport) -> str:
    if report.status.value == "incomplete":
        return "Resolve incomplete or unsupported evidence, then rerun the audit."
    if report.findings:
        return "Address the evidence-backed findings and rerun the affected evaluation."
    return "Review unresolved domain assumptions before approving the experiment."


__all__ = [
    "InvestigatorObservation",
    "InvestigatorAdapter",
    "InvestigatorRun",
    "InvestigatorSummary",
    "ReadOnlyInvestigatorContext",
    "build_deterministic_investigator_summary",
    "run_investigator",
]
