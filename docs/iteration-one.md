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

## Milestone 2: reproducible notebook runner

- Execute supported notebooks inside a restricted container
- Disable network access and enforce CPU, memory, process, and time limits
- Capture environment details, cell failures, outputs, and runtime
- Verify that a second execution reproduces the declared metric

## Milestone 3: experiment instrumentation

- Trace train/test split operations
- Trace preprocessing `fit` and `fit_transform` calls
- Trace estimator fitting, predictions, and metric calculations
- Associate every runtime event with its notebook cell
- Fingerprint datasets without exposing row values

## Milestone 4: deterministic validity checks

- Detect entity overlap across train and test partitions
- Detect preprocessing fitted before a split
- Expand metric checks with confusion-matrix evidence
- Add severity and confidence policies

## Milestone 5: independent counterfactual

- Replace a random row split with a configured group-isolated split
- Rerun the experiment
- Compare the original and counterfactual metrics
- Record the transformation and evidence

## Milestone 6: AI investigator

- Give one agent access only to structured audit tools
- Require evidence identifiers for every conclusion
- Reject unsupported generated findings
- Fall back to deterministic report templates when model output is invalid

## Validation gate

Before building a hosted SaaS, interview model reviewers at applied-ML teams or consultancies. Continue toward a commercial product only if real teams demonstrate recurring review work, provide pilot artifacts, and find that existing validation libraries do not cover the evidence and approval workflow.

