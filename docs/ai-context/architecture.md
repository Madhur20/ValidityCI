# Architecture and file map

## Control flow

```text
cli.main
  └─ audit_experiment
      ├─ ExperimentConfig.from_toml
      ├─ inspect_notebook
      ├─ profile_csv
      ├─ Runner.execute (optional, one or two observed runs plus counterfactual)
      │   └─ DockerRunner → container execute_notebook.py
      │       ├─ hidden instrumentation setup
      │       ├─ nbclient notebook execution
      │       ├─ hidden collector
      │       └─ ExecutionResult JSON
      ├─ run_metric_suitability_check
      ├─ run_entity_overlap_check (when executed)
      ├─ run_preprocessing_order_check (when executed)
      ├─ compare_executions (when two runs exist)
      ├─ compare_group_isolated_counterfactual (when requested)
      ├─ resolve_finding_policy (for every finding outcome)
      └─ AuditReport
          ├─ write_json
          └─ write_html
```

Static inspection always happens. Docker execution is optional, and valid static evidence is preserved when execution later fails.

## Source ownership map

| Path | Owns |
|---|---|
| `src/validityci/cli.py` | User-facing command and runner/resource selection. |
| `src/validityci/audit.py` | Top-level orchestration and final audit-status calculation. |
| `src/validityci/schemas/__init__.py` | Canonical immutable data contracts, validation, and serialization. |
| `src/validityci/models.py` | Compatibility re-exports; new code should import from `validityci.schemas`. |
| `src/validityci/notebook.py` | Safe notebook parsing and static cell search. |
| `src/validityci/dataset.py` | Safe local CSV profiling. |
| `src/validityci/checks/` | Deterministic validity checks; checks return evidence and findings. |
| `src/validityci/runner/protocol.py` | Backend-independent runner interface. |
| `src/validityci/runner/fake.py` | Deterministic test backend. |
| `src/validityci/runner/docker.py` | Host-side staging, Docker policy, timeouts, bounded result loading, and cleanup. |
| `docker/runner/Dockerfile` | Pinned execution environment and non-root user. |
| `docker/runner/execute_notebook.py` | Kernel instrumentation, notebook execution, normalization, and container result creation. |
| `src/validityci/reproducibility.py` | Comparison logic for two terminal execution results. |
| `src/validityci/differential.py` | Behavioral-equivalence comparison for instrumented and uninstrumented reference executions. |
| `src/validityci/counterfactual.py` | Validation and signed metric comparison for observed and group-isolated executions. |
| `src/validityci/policy.py` | Versioned severity/confidence catalog for supported finding outcomes. |
| `src/validityci/investigator_benchmark.py` | Strict benchmark catalog loader, deterministic baseline, and factual-support/usefulness scorer. |
| `src/validityci/investigator.py` | Read-only audit retrieval, deterministic fallback, provider-neutral adapter protocol, and strict output validation. |
| `src/validityci/investigator_fake.py` | Offline deterministic investigator adapter for provider-independent tests and evaluation. |
| `src/validityci/reporting.py` | JSON and HTML presentation only; it must not create new findings. |
| `benchmarks/investigator/` | Versioned investigator cases, expected observations/questions, unresolved assumptions, and forbidden claims. |
| `benchmarks/differential/` | Restricted live harness and failure fixture for instrumentation-transparency checks. |
| `tests/` | Dependency-free contracts, orchestration, runner, reporting, reproducibility, and trace tests. |
| `examples/` | Small declared experiments and the full instrumentation benchmark. |

## Dependency direction

- Schemas are the center of the system and should not import orchestration, runners, checks, or reporting.
- Audit orchestration depends on inspectors, checks, comparison, runner protocol, and schemas.
- Docker is one implementation of `Runner`; orchestration must not depend on Docker-specific behavior.
- Reporting consumes the completed `AuditReport`; it must not reinterpret evidence or change status.
- Container code emits JSON conforming to the host schema but is deliberately standalone inside the image.
- Investigator benchmarking consumes stable supporting-record IDs; it cannot change audit findings, policies, or report status.
- Metric artifact IDs are execution-local, so investigator support references qualify them as `<execution_id>/<metric_id>`.

## Runtime instrumentation model

The host never rewrites notebook source. The container inserts a setup cell before all original cells, a current-cell marker before each user code cell, and one collector after all original cells; synthetic cells are removed before output fingerprinting.

For differential verification only, the same runner can disable injection while preserving the image, input staging, and sandbox policy. The comparator accepts only equal successful output fingerprints or matching original-cell failures; infrastructure failures cannot establish transparency.

The setup wraps supported metric functions, `train_test_split`, `BaseCrossValidator.split`, scikit-learn's pinned iterable-CV wrapper, and estimator method access. Built-in and explicit iterable cross-validation folds are reconstructed with scikit-learn's safe indexing so later fit inputs match fold-training fingerprints; row indices are not exported. Metric wrappers retain scalar values plus aggregate binary confusion counts relative to the declared positive class; labels and predictions remain inside the kernel. Events are recorded when operations complete, so composite operations such as `fit_transform` can contain nested events before the enclosing event.

When an entity column is configured, split instrumentation looks only among values actually passed to `train_test_split`. It computes entity-set intersection inside the kernel and emits aggregate counts; `checks/entity_overlap.py` converts those aggregates into an explicit check result, evidence, and an optional finding.

Completed scikit-learn method events carry an `object_kind` of `transformer` or `estimator`. `checks/preprocessing_order.py` compares transformer-fit inputs with prior split inputs and outputs to classify train-only fitting, confirmed leakage, or lineage that needs review without exporting data values.

For the opt-in group counterfactual, the same setup cell replaces only supported `train_test_split` calls with `GroupShuffleSplit` during a separately labeled execution. It safe-indexes every positional array with the generated partitions, records the transformation and aggregate overlap, and leaves the source notebook untouched; the host compares its single captured primary metric with the observed baseline.
