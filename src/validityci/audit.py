from __future__ import annotations

from pathlib import Path

from validityci.counterfactual import compare_group_isolated_counterfactual
from validityci.policy import resolve_finding_policy
from validityci.checks.entity_overlap import run_entity_overlap_check
from validityci.checks.metric_suitability import run_metric_suitability_check
from validityci.checks.preprocessing_order import run_preprocessing_order_check
from validityci.dataset import profile_csv
from validityci.reproducibility import compare_executions
from validityci.runner.protocol import Runner
from validityci.schemas import (
    AuditReport,
    AuditStatus,
    CheckStatus,
    CounterfactualStatus,
    Evidence,
    ExecutionRequest,
    ExecutionStatus,
    ExecutionVariant,
    ExperimentConfig,
    Finding,
    MetricCaptureStatus,
    MetricSelector,
    ReproducibilityStatus,
    ResourceLimits,
)
from validityci.notebook import cells_containing, inspect_notebook


def audit_experiment(
    notebook_path: str | Path,
    data_path: str | Path,
    config_path: str | Path,
    *,
    runner: Runner | None = None,
    limits: ResourceLimits | None = None,
    execution_count: int = 1,
    group_counterfactual: bool = False,
) -> AuditReport:
    notebook_path = Path(notebook_path)
    data_path = Path(data_path)
    config = ExperimentConfig.from_toml(config_path)
    notebook = inspect_notebook(notebook_path)
    dataset = profile_csv(data_path, config.target_column)

    if execution_count not in {1, 2}:
        raise ValueError("execution_count must be 1 or 2")
    if group_counterfactual and runner is None:
        raise ValueError("group_counterfactual requires an execution runner")
    if group_counterfactual and config.entity_column is None:
        raise ValueError("group_counterfactual requires a configured entity_column")

    observed_executions = ()
    executions = ()
    if runner is not None:
        execution_ids = ("execution.original", "execution.repeated")
        observed_executions = tuple(
            runner.execute(
                ExecutionRequest(
                    execution_id=execution_ids[index],
                    notebook_path=str(notebook_path),
                    data_paths=(str(data_path),),
                    working_directory=str(notebook_path.parent),
                    metric_selector=MetricSelector(
                        metric_name=config.primary_metric,
                        variable_name=config.primary_metric_variable,
                    ),
                    entity_column=config.entity_column,
                    positive_class=config.positive_class,
                    random_seed=config.random_seed,
                    limits=limits or ResourceLimits(),
                    network_enabled=False,
                )
            )
            for index in range(execution_count)
        )
        executions = observed_executions
        if group_counterfactual:
            counterfactual_execution = runner.execute(
                ExecutionRequest(
                    execution_id="execution.counterfactual.group_isolated",
                    notebook_path=str(notebook_path),
                    data_paths=(str(data_path),),
                    working_directory=str(notebook_path.parent),
                    metric_selector=MetricSelector(
                        metric_name=config.primary_metric,
                        variable_name=config.primary_metric_variable,
                    ),
                    entity_column=config.entity_column,
                    positive_class=config.positive_class,
                    random_seed=config.random_seed,
                    execution_variant=(
                        ExecutionVariant.GROUP_ISOLATED_COUNTERFACTUAL
                    ),
                    limits=limits or ResourceLimits(),
                    network_enabled=False,
                )
            )
            executions = (*observed_executions, counterfactual_execution)

    metric_cells = cells_containing(
        notebook,
        ("accuracy_score", ".score(", "accuracy"),
    )
    evidence, findings = run_metric_suitability_check(
        config=config,
        dataset=dataset,
        metric_cells=metric_cells,
    )
    checks = ()
    if executions:
        entity_check, entity_evidence, entity_findings = run_entity_overlap_check(
            config, executions
        )
        preprocessing_check, preprocessing_evidence, preprocessing_findings = (
            run_preprocessing_order_check(executions)
        )
        checks = (entity_check, preprocessing_check)
        evidence = (*evidence, *entity_evidence, *preprocessing_evidence)
        findings = (*findings, *entity_findings, *preprocessing_findings)
    reproducibility = None
    if len(observed_executions) == 2:
        reproducibility = compare_executions(
            observed_executions[0], observed_executions[1], config.primary_metric
        )
        if reproducibility.status is ReproducibilityStatus.DIVERGED:
            policy = resolve_finding_policy(
                "reproducibility.repeated_execution", "diverged"
            )
            reproduction_evidence = Evidence(
                id="evidence.reproducibility.comparison",
                kind="reproducibility_comparison",
                summary="Two fresh executions produced different normalized results.",
                details=reproducibility.to_dict(),
                notebook_cells=tuple(
                    sorted(
                        {
                            metric.cell_index
                            for execution in executions
                            for metric in execution.metrics
                            if metric.cell_index is not None
                            and metric.metric_name == config.primary_metric
                        }
                    )
                ),
            )
            reproduction_finding = Finding(
                id="finding.reproducibility.diverged",
                check_id="reproducibility.repeated_execution",
                policy_id=policy.policy_id,
                policy_version=policy.version,
                title="Repeated executions produced different results",
                severity=policy.severity,
                confidence=policy.confidence,
                summary=(
                    "The primary metric, normalized notebook outputs, or execution "
                    "environment differed across two fresh runs."
                ),
                evidence_ids=(reproduction_evidence.id,),
                recommendation=(
                    "Inspect uncontrolled randomness, data ordering, external state, "
                    "parallel operations, and environment changes before relying on "
                    "the reported result."
                ),
            )
            evidence = (*evidence, reproduction_evidence)
            findings = (*findings, reproduction_finding)
    counterfactual = None
    if group_counterfactual:
        counterfactual = compare_group_isolated_counterfactual(
            observed_executions[0], executions[-1], config.primary_metric
        )
        counterfactual_evidence = Evidence(
            id="evidence.counterfactual.group_isolated",
            kind="group_isolated_counterfactual",
            summary=(
                "Compared the observed metric with a controlled group-isolated split."
                if counterfactual.status is CounterfactualStatus.COMPARED
                else "The group-isolated counterfactual could not be compared."
            ),
            details=counterfactual.to_dict(),
            notebook_cells=tuple(
                sorted(
                    {
                        event.cell_index
                        for execution in executions
                        if execution.runtime_trace is not None
                        for event in execution.runtime_trace.events
                        if event.event_type.value == "split"
                    }
                )
            ),
        )
        evidence = (*evidence, counterfactual_evidence)
    execution_failed = any(
        execution.status is not ExecutionStatus.SUCCEEDED
        for execution in executions
    )
    primary_metric_captured = any(
        metric.metric_name == config.primary_metric
        and metric.status is MetricCaptureStatus.CAPTURED
        for execution in executions
        for metric in execution.metrics
    )
    metric_capture_incomplete = bool(executions) and not primary_metric_captured
    comparison_incomplete = (
        reproducibility is not None
        and reproducibility.status is ReproducibilityStatus.INCOMPLETE
    )
    counterfactual_incomplete = (
        counterfactual is not None
        and counterfactual.status is CounterfactualStatus.INCOMPLETE
    )
    check_incomplete = any(
        check.status in {CheckStatus.UNSUPPORTED, CheckStatus.ERROR}
        for check in checks
    )
    if (
        execution_failed
        or metric_capture_incomplete
        or comparison_incomplete
        or counterfactual_incomplete
        or check_incomplete
    ):
        status = AuditStatus.INCOMPLETE
    elif findings:
        status = AuditStatus.ATTENTION_REQUIRED
    else:
        status = AuditStatus.PASSED_SUPPORTED_CHECKS
    return AuditReport(
        status=status,
        config=config,
        notebook=notebook,
        dataset=dataset,
        evidence=evidence,
        findings=findings,
        checks=checks,
        executions=executions,
        reproducibility=reproducibility,
        counterfactual=counterfactual,
    )
