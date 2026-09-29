"""Deterministic contract and scorer for the investigator evaluation benchmark."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

from validityci.schemas import AuditStatus, CheckStatus


INVESTIGATOR_BENCHMARK_SCHEMA_VERSION = "1.0.0"
INVESTIGATOR_RESPONSE_SCHEMA_VERSION = "1.0.0"


class BenchmarkCategory(StrEnum):
    CLEAN = "clean"
    FLAWED = "flawed"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    FAILURE = "failure"
    COUNTERFACTUAL = "counterfactual"


@dataclass(frozen=True, slots=True)
class ExpectedObservation:
    id: str
    summary: str
    evidence_ids: tuple[str, ...]
    deterministic_baseline: bool = True

    def __post_init__(self) -> None:
        _identifier(self.id, "observation ID")
        _non_empty(self.summary, "observation summary")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        if not self.evidence_ids:
            raise ValueError("Expected observations require at least one evidence ID")
        _unique(self.evidence_ids, "observation evidence IDs")
        for evidence_id in self.evidence_ids:
            _identifier(evidence_id, "observation evidence ID")
        if not isinstance(self.deterministic_baseline, bool):
            raise TypeError("deterministic_baseline must be a boolean")


@dataclass(frozen=True, slots=True)
class ReviewerQuestion:
    id: str
    question: str
    rationale: str

    def __post_init__(self) -> None:
        _identifier(self.id, "reviewer question ID")
        _non_empty(self.question, "reviewer question")
        _non_empty(self.rationale, "reviewer question rationale")


@dataclass(frozen=True, slots=True)
class UnresolvedAssumption:
    id: str
    summary: str

    def __post_init__(self) -> None:
        _identifier(self.id, "assumption ID")
        _non_empty(self.summary, "assumption summary")


@dataclass(frozen=True, slots=True)
class ForbiddenClaim:
    id: str
    claim: str

    def __post_init__(self) -> None:
        _identifier(self.id, "forbidden claim ID")
        _non_empty(self.claim, "forbidden claim")


@dataclass(frozen=True, slots=True)
class InvestigatorBenchmarkCase:
    id: str
    title: str
    category: BenchmarkCategory
    fixture: str
    expected_audit_status: AuditStatus
    expected_check_statuses: Mapping[str, CheckStatus]
    allowed_evidence_ids: tuple[str, ...]
    observations: tuple[ExpectedObservation, ...]
    reviewer_questions: tuple[ReviewerQuestion, ...]
    unresolved_assumptions: tuple[UnresolvedAssumption, ...]
    forbidden_claims: tuple[ForbiddenClaim, ...]

    def __post_init__(self) -> None:
        _identifier(self.id, "benchmark case ID")
        _non_empty(self.title, "benchmark case title")
        _non_empty(self.fixture, "benchmark fixture")
        object.__setattr__(
            self, "category", _enum(BenchmarkCategory, self.category, "category")
        )
        object.__setattr__(
            self,
            "expected_audit_status",
            _enum(AuditStatus, self.expected_audit_status, "expected audit status"),
        )
        check_statuses = {
            _identifier(check_id, "check ID"): _enum(
                CheckStatus, status, "expected check status"
            )
            for check_id, status in self.expected_check_statuses.items()
        }
        object.__setattr__(
            self, "expected_check_statuses", MappingProxyType(check_statuses)
        )
        object.__setattr__(
            self, "allowed_evidence_ids", tuple(self.allowed_evidence_ids)
        )
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "reviewer_questions", tuple(self.reviewer_questions))
        object.__setattr__(
            self, "unresolved_assumptions", tuple(self.unresolved_assumptions)
        )
        object.__setattr__(self, "forbidden_claims", tuple(self.forbidden_claims))
        _unique(self.allowed_evidence_ids, "allowed evidence IDs")
        for evidence_id in self.allowed_evidence_ids:
            _identifier(evidence_id, "allowed evidence ID")
        _unique((item.id for item in self.observations), "observation IDs")
        _unique((item.id for item in self.reviewer_questions), "question IDs")
        _unique((item.id for item in self.unresolved_assumptions), "assumption IDs")
        _unique((item.id for item in self.forbidden_claims), "forbidden claim IDs")
        if not self.observations:
            raise ValueError("Benchmark cases require expected observations")
        if not self.reviewer_questions:
            raise ValueError("Benchmark cases require reviewer questions")
        if not self.unresolved_assumptions:
            raise ValueError("Benchmark cases require unresolved assumptions")
        if not self.forbidden_claims:
            raise ValueError("Benchmark cases require forbidden claims")
        allowed = set(self.allowed_evidence_ids)
        for observation in self.observations:
            unknown = sorted(set(observation.evidence_ids) - allowed)
            if unknown:
                raise ValueError(
                    f"Observation {observation.id!r} references evidence outside "
                    f"the case allowlist: {', '.join(unknown)}"
                )


@dataclass(frozen=True, slots=True)
class InvestigatorBenchmark:
    cases: tuple[InvestigatorBenchmarkCase, ...]
    schema_version: str = INVESTIGATOR_BENCHMARK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != INVESTIGATOR_BENCHMARK_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported investigator benchmark schema {self.schema_version!r}"
            )
        object.__setattr__(self, "cases", tuple(self.cases))
        _unique((case.id for case in self.cases), "benchmark case IDs")
        if len(self.cases) < 10:
            raise ValueError("The investigator benchmark requires at least 10 cases")

    def case(self, case_id: str) -> InvestigatorBenchmarkCase:
        for case in self.cases:
            if case.id == case_id:
                return case
        raise KeyError(case_id)


@dataclass(frozen=True, slots=True)
class InvestigatorResponse:
    case_id: str
    observations: Mapping[str, tuple[str, ...]]
    reviewer_question_ids: tuple[str, ...] = ()
    unresolved_assumption_ids: tuple[str, ...] = ()
    asserted_forbidden_claim_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.case_id, "response case ID")
        normalized: dict[str, tuple[str, ...]] = {}
        for observation_id, evidence_ids in self.observations.items():
            _identifier(observation_id, "response observation ID")
            citations = tuple(evidence_ids)
            _unique(citations, "response evidence IDs")
            for evidence_id in citations:
                _identifier(evidence_id, "response evidence ID")
            normalized[observation_id] = citations
        object.__setattr__(self, "observations", MappingProxyType(normalized))
        object.__setattr__(
            self, "reviewer_question_ids", tuple(self.reviewer_question_ids)
        )
        object.__setattr__(
            self, "unresolved_assumption_ids", tuple(self.unresolved_assumption_ids)
        )
        object.__setattr__(
            self,
            "asserted_forbidden_claim_ids",
            tuple(self.asserted_forbidden_claim_ids),
        )
        _unique(self.reviewer_question_ids, "response question IDs")
        _unique(self.unresolved_assumption_ids, "response assumption IDs")
        for question_id in self.reviewer_question_ids:
            _identifier(question_id, "response question ID")
        for assumption_id in self.unresolved_assumption_ids:
            _identifier(assumption_id, "response assumption ID")
        _unique(
            self.asserted_forbidden_claim_ids,
            "response forbidden claim IDs",
        )
        for claim_id in self.asserted_forbidden_claim_ids:
            _identifier(claim_id, "response forbidden claim ID")


@dataclass(frozen=True, slots=True)
class InvestigatorBenchmarkScore:
    observation_recall: float
    evidence_link_accuracy: float
    reviewer_question_recall: float
    unresolved_assumption_recall: float
    unsupported_claim_rate: float
    usefulness_score: float
    passes_factual_support_gate: bool

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "observation_recall": self.observation_recall,
            "evidence_link_accuracy": self.evidence_link_accuracy,
            "reviewer_question_recall": self.reviewer_question_recall,
            "unresolved_assumption_recall": self.unresolved_assumption_recall,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "usefulness_score": self.usefulness_score,
            "passes_factual_support_gate": self.passes_factual_support_gate,
        }


@dataclass(frozen=True, slots=True)
class InvestigatorBenchmarkRun:
    benchmark_schema_version: str
    response_schema_version: str
    case_scores: Mapping[str, InvestigatorBenchmarkScore]
    factual_support_pass_rate: float
    mean_observation_recall: float
    mean_evidence_link_accuracy: float
    mean_reviewer_question_recall: float
    mean_unresolved_assumption_recall: float
    mean_unsupported_claim_rate: float
    mean_usefulness_score: float
    passes_release_gate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_schema_version": self.benchmark_schema_version,
            "response_schema_version": self.response_schema_version,
            "case_count": len(self.case_scores),
            "case_scores": {
                case_id: score.to_dict()
                for case_id, score in self.case_scores.items()
            },
            "aggregate": {
                "factual_support_pass_rate": self.factual_support_pass_rate,
                "mean_observation_recall": self.mean_observation_recall,
                "mean_evidence_link_accuracy": self.mean_evidence_link_accuracy,
                "mean_reviewer_question_recall": self.mean_reviewer_question_recall,
                "mean_unresolved_assumption_recall": (
                    self.mean_unresolved_assumption_recall
                ),
                "mean_unsupported_claim_rate": self.mean_unsupported_claim_rate,
                "mean_usefulness_score": self.mean_usefulness_score,
                "passes_release_gate": self.passes_release_gate,
            },
        }


def load_investigator_benchmark(path: str | Path) -> InvestigatorBenchmark:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("Investigator benchmark must contain a JSON object")
    _exact_fields(raw, {"schema_version", "cases"}, "investigator benchmark")
    cases_raw = _list(raw.get("cases"), "benchmark cases")
    return InvestigatorBenchmark(
        schema_version=_string(raw.get("schema_version"), "schema_version"),
        cases=tuple(_case(item) for item in cases_raw),
    )


def load_investigator_responses(path: str | Path) -> tuple[InvestigatorResponse, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("Investigator responses must contain a JSON object")
    _exact_fields(raw, {"schema_version", "responses"}, "investigator responses")
    version = _string(raw.get("schema_version"), "response schema_version")
    if version != INVESTIGATOR_RESPONSE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported investigator response schema {version!r}")
    return tuple(
        _response(value)
        for value in _list(raw.get("responses"), "investigator responses")
    )


def deterministic_baseline_response(
    case: InvestigatorBenchmarkCase,
) -> InvestigatorResponse:
    return InvestigatorResponse(
        case_id=case.id,
        observations={
            observation.id: observation.evidence_ids
            for observation in case.observations
            if observation.deterministic_baseline
        },
    )


def score_investigator_response(
    case: InvestigatorBenchmarkCase,
    response: InvestigatorResponse,
) -> InvestigatorBenchmarkScore:
    if response.case_id != case.id:
        raise ValueError("Response case ID does not match benchmark case")
    expected_observations = {item.id: item for item in case.observations}
    correct_observations = 0
    invalid_observations = 0
    for observation_id, citations in response.observations.items():
        expected = expected_observations.get(observation_id)
        if expected is None or set(citations) != set(expected.evidence_ids):
            invalid_observations += 1
        else:
            correct_observations += 1
    reported_count = len(response.observations)
    evidence_link_accuracy = _ratio(correct_observations, reported_count, empty=1.0)
    observation_recall = _ratio(
        correct_observations, len(expected_observations), empty=1.0
    )
    expected_questions = {item.id for item in case.reviewer_questions}
    selected_questions = set(response.reviewer_question_ids)
    expected_assumptions = {item.id for item in case.unresolved_assumptions}
    selected_assumptions = set(response.unresolved_assumption_ids)
    invalid_selections = len(selected_questions - expected_questions) + len(
        selected_assumptions - expected_assumptions
    )
    reviewer_question_recall = _ratio(
        len(selected_questions & expected_questions), len(expected_questions), empty=1.0
    )
    unresolved_assumption_recall = _ratio(
        len(selected_assumptions & expected_assumptions),
        len(expected_assumptions),
        empty=1.0,
    )
    asserted_forbidden_count = len(response.asserted_forbidden_claim_ids)
    unsupported_count = (
        invalid_observations + invalid_selections + asserted_forbidden_count
    )
    selection_count = (
        reported_count
        + len(selected_questions)
        + len(selected_assumptions)
        + asserted_forbidden_count
    )
    unsupported_claim_rate = _ratio(unsupported_count, selection_count, empty=0.0)
    usefulness_score = (
        observation_recall
        + reviewer_question_recall
        + unresolved_assumption_recall
    ) / 3.0
    return InvestigatorBenchmarkScore(
        observation_recall=observation_recall,
        evidence_link_accuracy=evidence_link_accuracy,
        reviewer_question_recall=reviewer_question_recall,
        unresolved_assumption_recall=unresolved_assumption_recall,
        unsupported_claim_rate=unsupported_claim_rate,
        usefulness_score=usefulness_score,
        passes_factual_support_gate=(
            evidence_link_accuracy == 1.0
            and unsupported_claim_rate == 0.0
            and invalid_selections == 0
            and asserted_forbidden_count == 0
        ),
    )


def score_investigator_benchmark(
    benchmark: InvestigatorBenchmark,
    responses: Sequence[InvestigatorResponse],
) -> InvestigatorBenchmarkRun:
    response_by_case: dict[str, InvestigatorResponse] = {}
    for response in responses:
        if response.case_id in response_by_case:
            raise ValueError(f"Duplicate response for case {response.case_id!r}")
        response_by_case[response.case_id] = response
    expected_ids = {case.id for case in benchmark.cases}
    supplied_ids = set(response_by_case)
    missing = sorted(expected_ids - supplied_ids)
    unknown = sorted(supplied_ids - expected_ids)
    if missing:
        raise ValueError(f"Missing benchmark responses: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"Unknown benchmark responses: {', '.join(unknown)}")
    scores = {
        case.id: score_investigator_response(case, response_by_case[case.id])
        for case in benchmark.cases
    }
    count = len(scores)

    def mean(attribute: str) -> float:
        return sum(float(getattr(score, attribute)) for score in scores.values()) / count

    factual_pass_rate = sum(
        score.passes_factual_support_gate for score in scores.values()
    ) / count
    unsupported_rate = mean("unsupported_claim_rate")
    evidence_accuracy = mean("evidence_link_accuracy")
    return InvestigatorBenchmarkRun(
        benchmark_schema_version=benchmark.schema_version,
        response_schema_version=INVESTIGATOR_RESPONSE_SCHEMA_VERSION,
        case_scores=MappingProxyType(scores),
        factual_support_pass_rate=factual_pass_rate,
        mean_observation_recall=mean("observation_recall"),
        mean_evidence_link_accuracy=evidence_accuracy,
        mean_reviewer_question_recall=mean("reviewer_question_recall"),
        mean_unresolved_assumption_recall=mean("unresolved_assumption_recall"),
        mean_unsupported_claim_rate=unsupported_rate,
        mean_usefulness_score=mean("usefulness_score"),
        passes_release_gate=(
            factual_pass_rate == 1.0
            and evidence_accuracy == 1.0
            and unsupported_rate == 0.0
        ),
    )


def deterministic_baseline_run(
    benchmark: InvestigatorBenchmark,
) -> InvestigatorBenchmarkRun:
    return score_investigator_benchmark(
        benchmark,
        tuple(deterministic_baseline_response(case) for case in benchmark.cases),
    )


def _case(raw: Any) -> InvestigatorBenchmarkCase:
    item = _mapping(raw, "benchmark case")
    fields = {
        "id",
        "title",
        "category",
        "fixture",
        "expected_audit_status",
        "expected_check_statuses",
        "allowed_evidence_ids",
        "observations",
        "reviewer_questions",
        "unresolved_assumptions",
        "forbidden_claims",
    }
    _exact_fields(item, fields, "benchmark case")
    checks = _mapping(item.get("expected_check_statuses"), "expected check statuses")
    return InvestigatorBenchmarkCase(
        id=_string(item.get("id"), "case id"),
        title=_string(item.get("title"), "case title"),
        category=_enum(
            BenchmarkCategory, _string(item.get("category"), "category"), "category"
        ),
        fixture=_string(item.get("fixture"), "fixture"),
        expected_audit_status=_enum(
            AuditStatus,
            _string(item.get("expected_audit_status"), "expected audit status"),
            "expected audit status",
        ),
        expected_check_statuses={
            str(check_id): _enum(
                CheckStatus,
                _string(status, "check status"),
                "expected check status",
            )
            for check_id, status in checks.items()
        },
        allowed_evidence_ids=tuple(
            _string(value, "allowed evidence ID")
            for value in _list(item.get("allowed_evidence_ids"), "allowed evidence IDs")
        ),
        observations=tuple(
            _observation(value)
            for value in _list(item.get("observations"), "observations")
        ),
        reviewer_questions=tuple(
            _question(value)
            for value in _list(item.get("reviewer_questions"), "reviewer questions")
        ),
        unresolved_assumptions=tuple(
            _assumption(value)
            for value in _list(
                item.get("unresolved_assumptions"), "unresolved assumptions"
            )
        ),
        forbidden_claims=tuple(
            _forbidden_claim(value)
            for value in _list(item.get("forbidden_claims"), "forbidden claims")
        ),
    )


def _response(raw: Any) -> InvestigatorResponse:
    item = _mapping(raw, "investigator response")
    fields = {
        "case_id",
        "observations",
        "reviewer_question_ids",
        "unresolved_assumption_ids",
        "asserted_forbidden_claim_ids",
    }
    _exact_fields(item, fields, "investigator response")
    observations = _mapping(item.get("observations"), "response observations")
    return InvestigatorResponse(
        case_id=_string(item.get("case_id"), "response case id"),
        observations={
            str(observation_id): tuple(
                _string(value, "response evidence ID")
                for value in _list(evidence_ids, "response evidence IDs")
            )
            for observation_id, evidence_ids in observations.items()
        },
        reviewer_question_ids=tuple(
            _string(value, "response question ID")
            for value in _list(
                item.get("reviewer_question_ids"), "response question IDs"
            )
        ),
        unresolved_assumption_ids=tuple(
            _string(value, "response assumption ID")
            for value in _list(
                item.get("unresolved_assumption_ids"), "response assumption IDs"
            )
        ),
        asserted_forbidden_claim_ids=tuple(
            _string(value, "response forbidden claim ID")
            for value in _list(
                item.get("asserted_forbidden_claim_ids"),
                "response forbidden claim IDs",
            )
        ),
    )


def _observation(raw: Any) -> ExpectedObservation:
    item = _mapping(raw, "observation")
    _exact_fields(
        item,
        {"id", "summary", "evidence_ids", "deterministic_baseline"},
        "observation",
    )
    baseline = item.get("deterministic_baseline")
    if not isinstance(baseline, bool):
        raise TypeError("deterministic_baseline must be a boolean")
    return ExpectedObservation(
        id=_string(item.get("id"), "observation id"),
        summary=_string(item.get("summary"), "observation summary"),
        evidence_ids=tuple(
            _string(value, "observation evidence ID")
            for value in _list(item.get("evidence_ids"), "observation evidence IDs")
        ),
        deterministic_baseline=baseline,
    )


def _question(raw: Any) -> ReviewerQuestion:
    item = _mapping(raw, "reviewer question")
    _exact_fields(item, {"id", "question", "rationale"}, "reviewer question")
    return ReviewerQuestion(
        id=_string(item.get("id"), "question id"),
        question=_string(item.get("question"), "question"),
        rationale=_string(item.get("rationale"), "question rationale"),
    )


def _assumption(raw: Any) -> UnresolvedAssumption:
    item = _mapping(raw, "unresolved assumption")
    _exact_fields(item, {"id", "summary"}, "unresolved assumption")
    return UnresolvedAssumption(
        id=_string(item.get("id"), "assumption id"),
        summary=_string(item.get("summary"), "assumption summary"),
    )


def _forbidden_claim(raw: Any) -> ForbiddenClaim:
    item = _mapping(raw, "forbidden claim")
    _exact_fields(item, {"id", "claim"}, "forbidden claim")
    return ForbiddenClaim(
        id=_string(item.get("id"), "forbidden claim id"),
        claim=_string(item.get("claim"), "forbidden claim"),
    )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be an array")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    _non_empty(value, label)
    return value


def _non_empty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} cannot be empty")


def _identifier(value: str, label: str) -> str:
    _non_empty(value, label)
    if any(character.isspace() for character in value):
        raise ValueError(f"{label} cannot contain whitespace")
    return value


def _unique(values: Sequence[str] | Any, label: str) -> None:
    normalized = tuple(values)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must be unique")


def _enum(enum_type: type[StrEnum], value: Any, label: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Unsupported {label}: {value!r}") from error


def _exact_fields(raw: Mapping[str, Any], expected: set[str], label: str) -> None:
    missing = sorted(expected - set(raw))
    unknown = sorted(set(raw) - expected)
    if missing:
        raise ValueError(f"Missing {label} fields: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"Unknown {label} fields: {', '.join(unknown)}")


def _ratio(numerator: int, denominator: int, *, empty: float) -> float:
    return empty if denominator == 0 else numerator / denominator


__all__ = [
    "INVESTIGATOR_BENCHMARK_SCHEMA_VERSION",
    "INVESTIGATOR_RESPONSE_SCHEMA_VERSION",
    "BenchmarkCategory",
    "ExpectedObservation",
    "ForbiddenClaim",
    "InvestigatorBenchmark",
    "InvestigatorBenchmarkCase",
    "InvestigatorBenchmarkScore",
    "InvestigatorBenchmarkRun",
    "InvestigatorResponse",
    "ReviewerQuestion",
    "UnresolvedAssumption",
    "deterministic_baseline_response",
    "deterministic_baseline_run",
    "load_investigator_benchmark",
    "load_investigator_responses",
    "score_investigator_benchmark",
    "score_investigator_response",
]
