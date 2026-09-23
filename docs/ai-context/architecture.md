# Architecture and file map

## Control flow

```text
cli.main
  └─ audit_experiment
      ├─ ExperimentConfig.from_toml
      ├─ inspect_notebook
      ├─ profile_csv
      ├─ Runner.execute (optional, once or twice)
      │   └─ DockerRunner → container execute_notebook.py
      │       ├─ hidden instrumentation setup
      │       ├─ nbclient notebook execution
      │       ├─ hidden collector
      │       └─ ExecutionResult JSON
      ├─ run_metric_suitability_check
      ├─ run_entity_overlap_check (when executed)
      ├─ run_preprocessing_order_check (when executed)
      ├─ compare_executions (when two runs exist)
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
| `src/validityci/reporting.py` | JSON and HTML presentation only; it must not create new findings. |
| `tests/` | Dependency-free contracts, orchestration, runner, reporting, reproducibility, and trace tests. |
| `examples/` | Small declared experiments and the full instrumentation benchmark. |

## Dependency direction

- Schemas are the center of the system and should not import orchestration, runners, checks, or reporting.
- Audit orchestration depends on inspectors, checks, comparison, runner protocol, and schemas.
- Docker is one implementation of `Runner`; orchestration must not depend on Docker-specific behavior.
- Reporting consumes the completed `AuditReport`; it must not reinterpret evidence or change status.
- Container code emits JSON conforming to the host schema but is deliberately standalone inside the image.

## Runtime instrumentation model

The host never rewrites notebook source. The container inserts a setup cell before all original cells, a current-cell marker before each user code cell, and one collector after all original cells; synthetic cells are removed before output fingerprinting.

The setup wraps supported metric and split functions and scikit-learn estimator method access. Events are recorded when operations complete, so composite operations such as `fit_transform` can contain nested events before the enclosing event.

When an entity column is configured, split instrumentation looks only among values actually passed to `train_test_split`. It computes entity-set intersection inside the kernel and emits aggregate counts; `checks/entity_overlap.py` converts those aggregates into an explicit check result, evidence, and an optional finding.

Completed scikit-learn method events carry an `object_kind` of `transformer` or `estimator`. `checks/preprocessing_order.py` compares transformer-fit inputs with prior split inputs and outputs to classify train-only fitting, confirmed leakage, or lineage that needs review without exporting data values.
