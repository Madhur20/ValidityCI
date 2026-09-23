# Iteration one roadmap

## Completed foundation

- Installable, dependency-free Python package
- Command-line audit workflow
- TOML experiment manifest
- Notebook and CSV inspection
- Structured evidence and findings
- Metric-suitability check
- JSON and HTML reports
- Automated tests and an intentionally flawed example
- Restricted Docker runner with explicit resource and network policy

## Milestone 2: reproducible notebook runner — completed

- Execute supported notebooks inside a restricted container — completed
- Disable network access and enforce CPU, memory, process, and time limits — implemented
- Capture cell failures, output fingerprints, and runtime — implemented
- Capture normalized scikit-learn metric artifacts with a manifest-variable fallback — implemented
- Capture a normalized environment fingerprint — implemented
- Compare two fresh executions across metrics, outputs, and environments — implemented

## Milestone 3: experiment instrumentation — initial supported surface completed

- Trace scikit-learn `train_test_split` operations — implemented
- Trace scikit-learn estimator and transformer `fit`, `fit_transform`, and `transform` calls — implemented
- Trace scikit-learn predictions and supported metric calculations — implemented
- Associate every supported runtime event with its original notebook cell — implemented
- Fingerprint datasets with run-scoped HMACs without storing row values or the key — implemented
- Trace supported `BaseCrossValidator` folds with fold-level lineage — implemented
- Apply entity-overlap and preprocessing-scope checks independently to every captured fold — implemented

Custom split functions, non-scikit-learn estimators, estimator `score`, and third-party metric libraries remain outside the supported surface and are not inferred.

## Milestone 4: deterministic validity checks

- Detect entity overlap across train and test partitions — initial supported implementation completed
- Detect preprocessing fitted before a split or on evaluation data — initial supported implementation completed
- Expand metric checks with confusion-matrix evidence — initial supported implementation completed
- Add explicit check statuses — implemented
- Centralize and version severity/confidence policies — initial implementation completed

## Milestone 5: independent counterfactual — initial supported surface completed

- Replace a supported random row split with a configured group-isolated split — implemented
- Rerun the experiment in a separately labeled restricted execution — implemented
- Compare exactly one original and counterfactual primary-metric call — implemented
- Record the transformation, signed delta, and privacy-minimized overlap evidence — implemented

Custom split functions, cross-validation counterfactuals, multiple primary-metric calls, and semantics such as stratification beyond group isolation remain explicit initial limits.

## Milestone 6: AI investigator

- Give one agent access only to structured audit tools
- Require evidence identifiers for every conclusion
- Reject unsupported generated findings
- Fall back to deterministic report templates when model output is invalid

## Validation gate

Before building a hosted SaaS, interview model reviewers at applied-ML teams or consultancies. Continue toward a commercial product only if real teams demonstrate recurring review work, provide pilot artifacts, and find that existing validation libraries do not cover the evidence and approval workflow.
