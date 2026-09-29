# Current state

Last reviewed: 2026-09-29

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
- Fold-level lineage for explicit iterable train/test index pairs through the pinned scikit-learn adapter, without serializing indices.
- Run-scoped HMAC data lineage containing types and shapes but no serialized row values or retained key.
- Versioned finding-policy catalog covering all five current deterministic finding outcomes.
- Opt-in group-isolated counterfactual execution for supported holdout splits, with explicit lineage, aggregate overlap evidence, and a signed primary-metric delta.
- Versioned investigator benchmark contract with 13 clean, flawed, ambiguous, unsupported, failure, CV, and counterfactual cases plus separate factual-support and usefulness scoring.
- Six immutable schema-valid investigator audit fixtures, an aggregate benchmark CLI, a read-only report retrieval surface, and a deterministic investigator fallback.
- Provider-neutral investigator adapter protocol, strict structured-output and citation validation, failure fallback, and an offline fake adapter.
- Permanent fallback snapshots for all six materialized reports and a 13-case adversarial response corpus that must fail every factual-support gate.
- Differential instrumentation comparator and restricted reference mode, live-verified for both successful output equivalence and original-cell failure equivalence.
- One hundred eleven dependency-free unit tests plus live Docker verification of instrumentation transparency, built-in and iterable cross-validation, entity overlap, preprocessing scope, aggregate confusion-matrix capture, and counterfactual execution.

## Versions

- Package version: `0.1.0` (packaging has not yet been aligned with runner milestones).
- Default runner image: `validityci-runner:0.6.0`.
- Audit report schema: `1.9.0`.
- Execution request/result schema: `1.8.0`.
- Runtime instrumentation schema: `1.6.0`.

Schema constants in `src/validityci/schemas/__init__.py` and `docker/runner/execute_notebook.py` are authoritative if this document becomes stale.

## Known support limits

- One notebook, one local CSV, binary classification, Python, pandas, NumPy, and scikit-learn.
- Fixed runner dependencies; no arbitrary installation, services, databases, GPUs, distributed execution, or network access.
- Runtime lineage covers `train_test_split`, splitters flowing through `BaseCrossValidator.split`, explicit iterable CV folds, and methods inherited through scikit-learn `BaseEstimator`; arbitrary custom splitter classes and third-party operations are not observed.
- Cross-validation lineage is verified for in-process execution; estimator/transformer events executed in joblib child processes are not yet collected.
- Entity overlap requires the configured entity DataFrame column or named Series to be passed to the supported split; otherwise the check is explicitly unsupported.
- Metric wrappers cover six named functions. Binary label-valued calls receive aggregate confusion counts; continuous scores, multiclass inputs, estimator `.score`, aliases imported before setup, custom functions, and third-party metrics need explicit handling or the manifest fallback.
- `fit_transform` produces nested fit, transform, and enclosing fit-transform completion events.
- HMAC fingerprints are comparable only inside one execution; deterministic checks analyze every run separately, while reproducibility compares metrics, outputs, and environments.
- The first counterfactual adapter covers only `train_test_split`, requires the configured entity data to participate, and compares exactly one captured primary-metric call; custom/CV splits and multiple metric calls remain incomplete.
- Docker materially reduces exposure but is not a sufficient boundary for hostile multi-tenant workloads.
- The package and image dependency chain is not yet fully locked by digest and hashes.
- Free-form provider output still needs a reviewed mapping to benchmark rubric concepts before model quality can be compared with the deterministic baseline.
- No external pilot or commercial demand has been validated.

## Next technical work

The next technical work is:

1. Add explicit lineage and fail-closed parallel handling for nested CV and search APIs.
2. Define the reviewed generated-response-to-rubric mapping needed to evaluate an external investigator provider.
3. Pin the runner image and Python dependency supply chain by digest and hashes.

Do not connect an external investigator model until adversarial evaluation preserves the factual-support gate.
