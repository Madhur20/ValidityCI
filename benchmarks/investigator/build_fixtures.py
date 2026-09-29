"""Build the canonical synthetic AuditReport fixtures for the investigator benchmark."""

from __future__ import annotations

import json
from pathlib import Path

from validityci.policy import resolve_finding_policy
from validityci.schemas import (
    AuditReport,
    AuditStatus,
    CheckResult,
    CheckStatus,
    CounterfactualComparison,
    CounterfactualStatus,
    DatasetProfile,
    Evidence,
    ExecutionFailure,
    ExecutionResult,
    ExecutionStatus,
    ExecutionVariant,
    ExperimentConfig,
    Finding,
    MetricArtifact,
    MetricCaptureMethod,
    MetricCaptureStatus,
    NotebookCell,
    NotebookSummary,
    ReproducibilityComparison,
    ReproducibilityStatus,
)


OUTPUT_DIRECTORY = Path(__file__).with_name("fixtures")


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for name, report in reports().items():
        (OUTPUT_DIRECTORY / f"{name}.json").write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def reports() -> dict[str, AuditReport]:
    return {
        "clean_supported_holdout": _clean_supported_holdout(),
        "reproducibility_divergence": _reproducibility_divergence(),
        "notebook_cell_failure": _notebook_cell_failure(),
        "unsupported_primary_metric": _unsupported_primary_metric(),
        "counterfactual_not_transformable": _counterfactual_not_transformable(),
        "ambiguous_transformer_lineage": _ambiguous_transformer_lineage(),
    }


def _clean_supported_holdout() -> AuditReport:
    entity = _evidence(
        "evidence.entity_overlap",
        "runtime_entity_overlap",
        "The supported holdout split had zero configured-entity overlap.",
    )
    preprocessing = _evidence(
        "evidence.preprocessing_fit_scope",
        "runtime_preprocessing_fit_scope",
        "The supported transformer fit matched the training partition.",
    )
    return _report(
        status=AuditStatus.PASSED_SUPPORTED_CHECKS,
        evidence=(entity, preprocessing),
        checks=(
            CheckResult(
                check_id="split.entity_overlap",
                status=CheckStatus.PASS,
                summary="No configured entities overlapped.",
                evidence_ids=(entity.id,),
            ),
            CheckResult(
                check_id="preprocessing.fit_scope",
                status=CheckStatus.PASS,
                summary="Supported preprocessing was fitted only on training data.",
                evidence_ids=(preprocessing.id,),
            ),
        ),
        executions=(_success("execution.original", 0.8),),
    )


def _reproducibility_divergence() -> AuditReport:
    evidence = _evidence(
        "evidence.reproducibility.comparison",
        "reproducibility_comparison",
        "Two fresh executions produced different normalized results.",
    )
    policy = resolve_finding_policy(
        "reproducibility.repeated_execution", "diverged"
    )
    comparison = ReproducibilityComparison(
        status=ReproducibilityStatus.DIVERGED,
        baseline_execution_id="execution.original",
        repeated_execution_id="execution.repeated",
        primary_metric="accuracy",
        baseline_metric_values=(0.8,),
        repeated_metric_values=(0.7,),
        metric_match=False,
        output_match=False,
        environment_match=True,
        max_absolute_delta=0.1,
        reasons=("Primary metric values differed", "Output fingerprints differed"),
    )
    finding = Finding(
        id="finding.reproducibility.diverged",
        check_id="reproducibility.repeated_execution",
        policy_id=policy.policy_id,
        policy_version=policy.version,
        title="Repeated executions produced different results",
        severity=policy.severity,
        confidence=policy.confidence,
        summary="Two fresh executions disagreed on metrics and normalized outputs.",
        evidence_ids=(evidence.id,),
        recommendation="Identify uncontrolled state before relying on the result.",
    )
    return _report(
        status=AuditStatus.ATTENTION_REQUIRED,
        evidence=(evidence,),
        findings=(finding,),
        executions=(
            _success("execution.original", 0.8, fingerprint="sha256:first"),
            _success("execution.repeated", 0.7, fingerprint="sha256:second"),
        ),
        reproducibility=comparison,
    )


def _notebook_cell_failure() -> AuditReport:
    execution = ExecutionResult(
        execution_id="execution.original",
        status=ExecutionStatus.CELL_FAILED,
        duration_ms=5,
        failure=ExecutionFailure(
            kind="notebook_cell_error",
            message="NameError: missing_model",
            cell_index=1,
        ),
    )
    return _report(
        status=AuditStatus.INCOMPLETE,
        checks=(
            CheckResult(
                check_id="split.entity_overlap",
                status=CheckStatus.ERROR,
                summary="Entity overlap could not run because execution failed.",
            ),
            CheckResult(
                check_id="preprocessing.fit_scope",
                status=CheckStatus.ERROR,
                summary="Preprocessing analysis could not run because execution failed.",
            ),
        ),
        executions=(execution,),
    )


def _unsupported_primary_metric() -> AuditReport:
    metric = MetricArtifact(
        id="metric.1",
        metric_name="accuracy",
        status=MetricCaptureStatus.UNSUPPORTED,
        capture_method=MetricCaptureMethod.NOT_OBSERVED,
        reason="No supported runtime call or manifest variable was observed.",
    )
    execution = ExecutionResult(
        execution_id="execution.original",
        status=ExecutionStatus.SUCCEEDED,
        duration_ms=5,
        output_fingerprint="sha256:unsupported-metric",
        metrics=(metric,),
    )
    return _report(status=AuditStatus.INCOMPLETE, executions=(execution,))


def _counterfactual_not_transformable() -> AuditReport:
    baseline = _success("execution.original", 0.8)
    counterfactual = _success(
        "execution.counterfactual.group_isolated",
        0.8,
        variant=ExecutionVariant.GROUP_ISOLATED_COUNTERFACTUAL,
    )
    comparison = CounterfactualComparison(
        status=CounterfactualStatus.INCOMPLETE,
        baseline_execution_id=baseline.execution_id,
        counterfactual_execution_id=counterfactual.execution_id,
        primary_metric="accuracy",
        transformation_count=0,
        baseline_metric_value=0.8,
        counterfactual_metric_value=0.8,
        reason="No supported train/test split was transformed.",
    )
    evidence = Evidence(
        id="evidence.counterfactual.group_isolated",
        kind="group_isolated_counterfactual",
        summary="The requested counterfactual could not transform a supported split.",
        details=comparison.to_dict(),
    )
    return _report(
        status=AuditStatus.INCOMPLETE,
        evidence=(evidence,),
        executions=(baseline, counterfactual),
        counterfactual=comparison,
    )


def _ambiguous_transformer_lineage() -> AuditReport:
    evidence = _evidence(
        "evidence.preprocessing_fit_scope",
        "runtime_preprocessing_fit_scope",
        "A transformer fit input did not match a captured partition.",
    )
    policy = resolve_finding_policy(
        "preprocessing.fit_scope", "unverified_fit_scope"
    )
    finding = Finding(
        id="finding.preprocessing_fit_scope_review",
        check_id="preprocessing.fit_scope",
        policy_id=policy.policy_id,
        policy_version=policy.version,
        title="Preprocessing fit scope could not be established",
        severity=policy.severity,
        confidence=policy.confidence,
        summary="The transformer input did not match captured train, test, or full data.",
        evidence_ids=(evidence.id,),
        recommendation="Make the derived training-data lineage explicit.",
    )
    return _report(
        status=AuditStatus.ATTENTION_REQUIRED,
        evidence=(evidence,),
        findings=(finding,),
        checks=(
            CheckResult(
                check_id="preprocessing.fit_scope",
                status=CheckStatus.REVIEW,
                summary="Transformer fit scope requires reviewer confirmation.",
                evidence_ids=(evidence.id,),
            ),
        ),
        executions=(_success("execution.original", 0.8),),
    )


def _report(
    *,
    status: AuditStatus,
    evidence: tuple[Evidence, ...] = (),
    findings: tuple[Finding, ...] = (),
    checks: tuple[CheckResult, ...] = (),
    executions: tuple[ExecutionResult, ...] = (),
    reproducibility: ReproducibilityComparison | None = None,
    counterfactual: CounterfactualComparison | None = None,
) -> AuditReport:
    return AuditReport(
        status=status,
        config=ExperimentConfig(
            task_type="binary_classification",
            target_column="target",
            primary_metric="accuracy",
            entity_column="entity_id",
        ),
        notebook=NotebookSummary(
            path="synthetic.ipynb",
            total_cells=1,
            code_cells=1,
            markdown_cells=0,
            cells=(
                NotebookCell(
                    index=0,
                    cell_type="code",
                    source="# Synthetic investigator benchmark fixture",
                ),
            ),
        ),
        dataset=DatasetProfile(
            path="synthetic.csv",
            row_count=20,
            columns=("entity_id", "feature", "target"),
            target_column="target",
            class_counts={"0": 15, "1": 5},
            minority_fraction=0.25,
        ),
        evidence=evidence,
        findings=findings,
        checks=checks,
        executions=executions,
        reproducibility=reproducibility,
        counterfactual=counterfactual,
    )


def _success(
    execution_id: str,
    value: float,
    *,
    fingerprint: str = "sha256:stable",
    variant: ExecutionVariant = ExecutionVariant.OBSERVED,
) -> ExecutionResult:
    return ExecutionResult(
        execution_id=execution_id,
        status=ExecutionStatus.SUCCEEDED,
        duration_ms=5,
        output_fingerprint=fingerprint,
        metrics=(
            MetricArtifact(
                id="metric.1",
                metric_name="accuracy",
                status=MetricCaptureStatus.CAPTURED,
                capture_method=MetricCaptureMethod.RUNTIME_WRAPPER,
                value=value,
                cell_index=0,
                sample_count=5,
            ),
        ),
        execution_variant=variant,
    )


def _evidence(evidence_id: str, kind: str, summary: str) -> Evidence:
    return Evidence(
        id=evidence_id,
        kind=kind,
        summary=summary,
        details={"synthetic_fixture": True},
        notebook_cells=(0,),
    )


if __name__ == "__main__":
    main()
