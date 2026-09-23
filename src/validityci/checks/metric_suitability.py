from __future__ import annotations

from validityci.policy import resolve_finding_policy
from validityci.schemas import (
    DatasetProfile,
    Evidence,
    ExperimentConfig,
    Finding,
)


CHECK_ID = "metric_suitability.class_imbalance"


def run_metric_suitability_check(
    config: ExperimentConfig,
    dataset: DatasetProfile,
    metric_cells: tuple[int, ...],
) -> tuple[tuple[Evidence, ...], tuple[Finding, ...]]:
    if config.primary_metric != "accuracy" or dataset.minority_fraction >= 0.20:
        return (), ()

    evidence = Evidence(
        id="evidence.class_distribution",
        kind="dataset_profile",
        summary=(
            f"The minority class represents {dataset.minority_fraction:.1%} of "
            f"{dataset.row_count} rows."
        ),
        details={
            "class_counts": dataset.class_counts,
            "minority_fraction": dataset.minority_fraction,
            "declared_primary_metric": config.primary_metric,
        },
        notebook_cells=metric_cells,
    )
    policy = resolve_finding_policy(CHECK_ID, "accuracy_on_imbalanced_target")
    finding = Finding(
        id="finding.metric_accuracy_imbalance",
        check_id=CHECK_ID,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        title="Accuracy may hide minority-class failures",
        severity=policy.severity,
        confidence=policy.confidence,
        summary=(
            "The experiment declares accuracy as its primary metric even though "
            "the target is substantially imbalanced."
        ),
        evidence_ids=(evidence.id,),
        recommendation=(
            "Report precision, recall, F1, balanced accuracy, and a confusion matrix. "
            "Choose the primary metric from the cost of false positives and false negatives."
        ),
    )
    return (evidence,), (finding,)
