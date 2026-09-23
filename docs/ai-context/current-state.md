# Current state

Last reviewed: 2026-09-23

## Product boundary

ValidityCI is an independent, local-first validation gate for notebook-based tabular ML experiments. It is not a general code reviewer, a certification system, a hosted MLOps platform, or proof that a model is universally correct.

## Implemented

- Dependency-free CLI, TOML manifest loading, notebook inspection, CSV profiling, JSON reports, and HTML reports.
- Deterministic checks for accuracy suitability on an imbalanced target, configured entity overlap, and preprocessing fit scope across supported splits.
- Runner protocol plus deterministic fake runner for fast orchestration tests.
- Restricted Docker execution with declared-input staging, network denial, non-root execution, read-only root/input, and CPU, memory, process, output, cell, and wall-time limits.
- Structured cell failures, timeouts, runner failures, normalized user-output fingerprints, and cleanup of timed-out containers.
- Structured capture for six scikit-learn metrics, privacy-minimized binary confusion counts, and one explicit manifest-variable fallback.
- Two fresh executions by default, environment fingerprints, and separate metric/output/environment comparisons.
- Versioned runtime events for supported split, fit, transform, predict, and metric calls with original cell attribution.
- Fold-level lineage for supported scikit-learn cross-validation splitters, including group-overlap and per-fold preprocessing analysis.
- Run-scoped HMAC data lineage containing types and shapes but no serialized row values or retained key.
- Versioned finding-policy catalog covering all five current deterministic finding outcomes.
- Opt-in group-isolated counterfactual execution for supported holdout splits, with explicit lineage, aggregate overlap evidence, and a signed primary-metric delta.
- Eighty dependency-free unit tests plus live Docker verification of entity overlap, preprocessing scope, cross-validation folds, aggregate confusion-matrix capture, and counterfactual execution.

## Versions

- Package version: `0.1.0` (packaging has not yet been aligned with runner milestones).
- Default runner image: `validityci-runner:0.6.0`.
- Audit report schema: `1.9.0`.
- Execution request/result schema: `1.8.0`.
- Runtime instrumentation schema: `1.5.0`.

Schema constants in `src/validityci/schemas/__init__.py` and `docker/runner/execute_notebook.py` are authoritative if this document becomes stale.

## Known support limits

- One notebook, one local CSV, binary classification, Python, pandas, NumPy, and scikit-learn.
- Fixed runner dependencies; no arbitrary installation, services, databases, GPUs, distributed execution, or network access.
- Runtime lineage covers `train_test_split`, splitters flowing through `BaseCrossValidator.split`, and methods inherited through scikit-learn `BaseEstimator`; custom and third-party operations are not observed.
- Cross-validation lineage is verified for in-process execution; estimator/transformer events executed in joblib child processes are not yet collected.
- Entity overlap requires the configured entity DataFrame column or named Series to be passed to the supported split; otherwise the check is explicitly unsupported.
- Metric wrappers cover six named functions. Binary label-valued calls receive aggregate confusion counts; continuous scores, multiclass inputs, estimator `.score`, aliases imported before setup, custom functions, and third-party metrics need explicit handling or the manifest fallback.
- `fit_transform` produces nested fit, transform, and enclosing fit-transform completion events.
- HMAC fingerprints are comparable only inside one execution; deterministic checks analyze every run separately, while reproducibility compares metrics, outputs, and environments.
- The first counterfactual adapter covers only `train_test_split`, requires the configured entity data to participate, and compares exactly one captured primary-metric call; custom/CV splits and multiple metric calls remain incomplete.
- Docker materially reduces exposure but is not a sufficient boundary for hostile multi-tenant workloads.
- The package and image dependency chain is not yet fully locked by digest and hashes.
- No external pilot or commercial demand has been validated.

## Next technical work

The next technical work is:

1. Investigator benchmark over the permanent clean, flawed, ambiguous, unsupported, and counterfactual cases.
2. Cross-validation adapter expansion for custom iterable splitters, nested CV, and search APIs.
3. Differential instrumentation tests that compare instrumented and uninstrumented notebook behavior.

Do not add an AI investigator before deterministic checks and an investigator evaluation benchmark exist.
