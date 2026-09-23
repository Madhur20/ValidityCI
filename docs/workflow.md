# ValidityCI project workflow

ValidityCI is a local-first verification layer for supported tabular machine-learning notebooks. It combines safe static inspection with optional repeated execution in restricted containers, then produces structured evidence instead of claiming that a passing report proves universal model correctness.

## End-to-end flow

```text
Notebook + CSV + TOML manifest
             │
             ▼
       CLI input parsing
             │
             ▼
  Static notebook/data inspection ───────┐
             │                            │
             ├── optional Docker run 1    │
             ├── optional Docker run 2    │
             ├── optional group-isolated  │
             │   counterfactual run       │
             │          │                 │
             │          ▼                 │
             │   metrics + outputs +      │
             │   environment + trace      │
             │          │                 │
             │          ▼                 │
             │   reproducibility compare  │
             │                            │
             └────────────────────────────┘
                          │
                          ▼
                evidence and findings
                          │
                          ▼
                JSON and HTML reports
```

## Workflow stages

1. **Declare the experiment.** The reviewer supplies a notebook, local CSV, and TOML manifest containing the task, target, primary metric, and optional semantic fields.
2. **Inspect without executing.** ValidityCI parses notebook cells, profiles the target distribution, and runs the deterministic metric-suitability check.
3. **Execute when requested.** With `--execute`, the audit creates one or two observed execution requests and sends each to a fresh restricted Docker container; an opted-in counterfactual adds one more container.
4. **Instrument the kernel.** Hidden setup and collector cells observe supported split, fit, transform, predict, and metric operations without rewriting user source.
5. **Normalize evidence.** The runner returns metric artifacts, notebook-output and environment fingerprints, failures, and a privacy-minimized runtime trace.
6. **Compare repeated runs.** Two observed executions are compared independently across ordered metric values, normalized outputs, and environment fingerprints.
7. **Run an optional counterfactual.** With `--group-counterfactual`, one extra labeled execution replaces supported holdout splitting with an in-memory group-isolated split and compares exactly one primary-metric call with the observed baseline.
8. **Assemble the audit.** Static evidence, execution results, reproducibility and counterfactual evidence, and findings are combined under strict status rules.
9. **Write reports.** The same immutable audit model is serialized to machine-readable JSON and a reviewer-oriented HTML report.

## Main components

Each component below is described in one or two lines, with its primary implementation location.

| Component | Responsibility and mechanism | Location |
|---|---|---|
| CLI | Parses the `audit` command, execution flags, resource limits, and output paths; it constructs the selected runner and writes both reports. | `src/validityci/cli.py` |
| Audit orchestrator | Coordinates configuration loading, static inspection, optional executions, checks, comparison, and final status selection. | `src/validityci/audit.py` |
| Experiment configuration | Reads the TOML `[experiment]` contract and validates task, target, metric, optional entity/timestamp fields, and seed. | `ExperimentConfig` in `src/validityci/schemas/` |
| Notebook inspector | Parses notebook JSON into indexed immutable cells and locates cells containing terms relevant to static checks. | `src/validityci/notebook.py` |
| Dataset profiler | Reads the declared CSV without third-party dependencies and computes row count, columns, target counts, and class proportions. | `src/validityci/dataset.py` |
| Metric-suitability check | Warns when accuracy is declared for a sufficiently imbalanced binary target and links the finding to data evidence and notebook cells. | `src/validityci/checks/metric_suitability.py` |
| Entity-overlap check | Consumes aggregate split instrumentation and blocks when configured entities appear in both train and test partitions; unsupported lineage remains explicit. | `src/validityci/checks/entity_overlap.py` |
| Preprocessing-order check | Correlates transformer-fit inputs with split lineage and blocks fitting before the split or on full/test data; ambiguous lineage requires review. | `src/validityci/checks/preprocessing_order.py` |
| Runner protocol | Defines the small request/result boundary used by audit orchestration, independent of any execution backend. | `src/validityci/runner/protocol.py` |
| Fake runner | Returns preconfigured immutable results for fast orchestration and failure tests without requiring Docker. | `src/validityci/runner/fake.py` |
| Docker runner | Stages only declared inputs, applies isolation/resource flags, starts the pinned image, bounds results, and converts launch problems into structured failures. | `src/validityci/runner/docker.py` |
| Container entry point | Executes the notebook with `nbclient`, injects hidden instrumentation cells, normalizes outputs, and emits a versioned result JSON. | `docker/runner/execute_notebook.py` |
| Metric capture | Wraps six supported `sklearn.metrics` functions, captures scalar results and privacy-minimized binary confusion counts, and falls back to one explicitly named finite variable when necessary. | Container instrumentation source |
| Runtime instrumentation | Observes supported holdout, cross-validation, and `BaseEstimator` method calls, attaches original cell/fold indexes, and records ordered input/output lineage events. | Container instrumentation source |
| Data fingerprinting | Uses a fresh per-execution HMAC key over canonical data representations so data can be linked within a run without serializing rows or exporting the key. | Container instrumentation source |
| Output fingerprinting | Hashes normalized user-cell outputs after removing synthetic cells and transient execution metadata. | Container entry point |
| Environment fingerprinting | Hashes installed package names/versions and runner code, then combines them with basic Python and platform fields. | Container entry point |
| Reproducibility comparison | Compares ordered primary-metric calls with a strict tolerance while preserving output and environment equality as separate signals. | `src/validityci/reproducibility.py` |
| Counterfactual comparison | Validates explicit observed/counterfactual lineage and computes a signed metric delta only after a supported group-isolated transformation. | `src/validityci/counterfactual.py` |
| Finding policy | Maps supported check outcomes to reviewed severity/confidence decisions and gives every finding a stable policy ID and version. | `src/validityci/policy.py` |
| Schemas and invariants | Provides immutable, versioned request, result, trace, evidence, finding, comparison, and report models with strict JSON round trips. | `src/validityci/schemas/__init__.py` |
| Report writers | Serializes the audit to JSON and renders execution, trace, reproducibility, evidence, and findings into standalone HTML. | `src/validityci/reporting.py` |
| Tests and benchmarks | Unit tests cover contracts and orchestration; example notebooks provide clean, flawed, and unsupported static, holdout, reproducibility, and cross-validation cases. | `tests/` and `examples/` |
| Engineering memory | Records decisions, observed hurdles, open assumptions, anticipated failures, and claims that must not be overstated. | `docs/engineering-notes/` |

## Status rules

| Status | Meaning |
|---|---|
| `passed_supported_checks` | Every requested supported phase completed and produced no findings. It is not a universal correctness claim. |
| `attention_required` | Supported evidence produced at least one finding or a reproducibility divergence. |
| `incomplete` | Execution failed, the primary metric was unsupported, or a requested reproducibility/counterfactual comparison was unavailable. |

Infrastructure failure is never presented as an invalid experiment, and unsupported behavior is never converted into a pass.

Individual deterministic checks separately use `pass`, `fail`, `review`, `not_applicable`, `unsupported`, and `error`. An unsupported or errored requested runtime check makes the overall audit incomplete.

Finding impact is separate from check status. The versioned policy catalog currently assigns blocking/high only to directly confirmed runtime leakage, warning/medium to ambiguous lineage review, and warning/high to directly observed but context-dependent metric or reproducibility concerns.

## Execution and privacy boundary

- Docker execution is opt-in; ValidityCI never silently falls back to running notebook code on the host.
- Only the declared notebook and data files are staged. The container has no network, a read-only root, a non-root user, dropped capabilities, and explicit resource limits.
- Reports contain aggregates, scalar metric evidence, and fingerprints—not raw CSV rows or full notebook output values.
- Runtime data fingerprints are intentionally scoped to one execution. Separate runs use different keys, so trace structure is comparable across runs but fingerprint values are not.
- Counterfactual splitting uses entity values only inside the kernel; reports retain transformation metadata and overlap aggregates, not group values or row indices.

## Current supported surface

- Python notebooks using pandas and scikit-learn in the pinned CPU-only image.
- One local CSV and binary-classification manifest.
- `train_test_split`, `BaseCrossValidator` fold generation, and scikit-learn estimator/transformer `fit`, `fit_transform`, `transform`, and `predict` events.
- `accuracy`, `balanced_accuracy`, `f1`, `precision`, `recall`, and `roc_auc` metric wrappers.
- Aggregate binary confusion matrices for label-valued metric calls using the configured positive class; unsupported score/multiclass inputs remain explicit.
- Static metric suitability, repeated execution comparison, JSON reporting, and HTML reporting.
- Aggregate entity-overlap detection when the configured entity column participates in a supported split.
- Preprocessing fit-scope detection for supported scikit-learn transformers and `train_test_split` lineage.
- Opt-in `train_test_split` replacement with `GroupShuffleSplit` plus an observed-to-counterfactual primary-metric delta.

Custom split functions, cross-validation splitters that bypass `BaseCrossValidator.split`, parallel CV work executed in child processes, non-scikit-learn estimators, estimator `.score`, hand-written metrics, third-party metric libraries, distributed training, databases, and arbitrary dependency installation remain outside the initial support boundary.

## Typical commands

Static audit:

```bash
PYTHONPATH=src python3 -m validityci audit examples/imbalanced_churn.ipynb \
  --data examples/customer_churn.csv \
  --config examples/validityci.toml \
  --output build/example-audit.json \
  --html build/example-audit.html
```

Build and use the restricted runner:

```bash
docker build -f docker/runner/Dockerfile -t validityci-runner:0.6.0 .
PYTHONPATH=src python3 -m validityci audit examples/runtime_instrumentation.ipynb \
  --data examples/customer_churn.csv \
  --config examples/validityci.toml \
  --execute --runs 2 \
  --output build/runtime-audit.json \
  --html build/runtime-audit.html
```

Run the group-isolated counterfactual benchmark:

```bash
PYTHONPATH=src python3 -m validityci audit examples/entity_overlap.ipynb \
  --data examples/entity_overlap.csv \
  --config examples/validityci.toml \
  --execute --runs 1 --group-counterfactual \
  --output build/counterfactual-audit.json \
  --html build/counterfactual-audit.html
```

Run the dependency-free unit suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
