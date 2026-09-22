from __future__ import annotations

from pathlib import Path

from validityci.checks.metric_suitability import run_metric_suitability_check
from validityci.dataset import profile_csv
from validityci.runner.protocol import Runner
from validityci.schemas import (
    AuditReport,
    AuditStatus,
    ExecutionRequest,
    ExecutionStatus,
    ExperimentConfig,
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
) -> AuditReport:
    notebook_path = Path(notebook_path)
    data_path = Path(data_path)
    config = ExperimentConfig.from_toml(config_path)
    notebook = inspect_notebook(notebook_path)
    dataset = profile_csv(data_path, config.target_column)

    executions = ()
    if runner is not None:
        request = ExecutionRequest(
            execution_id="execution.original",
            notebook_path=str(notebook_path),
            data_paths=(str(data_path),),
            working_directory=str(notebook_path.parent),
            limits=limits or ResourceLimits(),
            network_enabled=False,
        )
        executions = (runner.execute(request),)

    metric_cells = cells_containing(
        notebook,
        ("accuracy_score", ".score(", "accuracy"),
    )
    evidence, findings = run_metric_suitability_check(
        config=config,
        dataset=dataset,
        metric_cells=metric_cells,
    )
    execution_failed = any(
        execution.status is not ExecutionStatus.SUCCEEDED
        for execution in executions
    )
    if execution_failed:
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
        executions=executions,
    )
