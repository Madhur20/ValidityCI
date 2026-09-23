"""Versioned severity and confidence decisions for deterministic findings."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from validityci.schemas import Confidence, Severity


FINDING_POLICY_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class FindingPolicy:
    policy_id: str
    severity: Severity
    confidence: Confidence
    rationale: str
    version: str = FINDING_POLICY_VERSION


_POLICIES = MappingProxyType(
    {
        ("metric_suitability.class_imbalance", "accuracy_on_imbalanced_target"): FindingPolicy(
            policy_id="policy.metric_accuracy_imbalance",
            severity=Severity.WARNING,
            confidence=Confidence.HIGH,
            rationale=(
                "The dataset profile and declared metric directly establish the "
                "condition, but metric suitability depends on error costs."
            ),
        ),
        ("split.entity_overlap", "confirmed_overlap"): FindingPolicy(
            policy_id="policy.entity_overlap_confirmed",
            severity=Severity.BLOCKING,
            confidence=Confidence.HIGH,
            rationale=(
                "In-kernel aggregate intersection directly confirms configured "
                "entities in both evaluation partitions."
            ),
        ),
        ("preprocessing.fit_scope", "confirmed_leakage"): FindingPolicy(
            policy_id="policy.preprocessing_leakage_confirmed",
            severity=Severity.BLOCKING,
            confidence=Confidence.HIGH,
            rationale=(
                "Runtime fingerprints directly link transformer fitting to pre-split "
                "or held-out data."
            ),
        ),
        ("preprocessing.fit_scope", "unverified_fit_scope"): FindingPolicy(
            policy_id="policy.preprocessing_lineage_review",
            severity=Severity.WARNING,
            confidence=Confidence.MEDIUM,
            rationale=(
                "A transformer fit was observed, but supported lineage cannot prove "
                "whether its derived input is safe or leaky."
            ),
        ),
        ("reproducibility.repeated_execution", "diverged"): FindingPolicy(
            policy_id="policy.reproducibility_divergence",
            severity=Severity.WARNING,
            confidence=Confidence.HIGH,
            rationale=(
                "Two fresh executions directly disagree, while the practical impact "
                "requires reviewer context."
            ),
        ),
    }
)


def resolve_finding_policy(check_id: str, outcome: str) -> FindingPolicy:
    try:
        return _POLICIES[(check_id, outcome)]
    except KeyError as error:
        raise ValueError(
            f"No finding policy is registered for {check_id!r}/{outcome!r}"
        ) from error


def finding_policies() -> tuple[FindingPolicy, ...]:
    """Return the immutable policy catalog in deterministic key order."""

    return tuple(_POLICIES[key] for key in sorted(_POLICIES))


__all__ = [
    "FINDING_POLICY_VERSION",
    "FindingPolicy",
    "finding_policies",
    "resolve_finding_policy",
]
