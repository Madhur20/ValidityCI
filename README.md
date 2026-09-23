# ValidityCI

ValidityCI is an independent verification layer for machine-learning experiments. It is intended to reproduce an experiment, run deterministic validity checks, and produce an evidence-backed report before a result is approved or delivered.

This repository contains a static audit and an opt-in restricted notebook runner. The static path safely reads a notebook, profiles a local CSV, checks whether the declared primary metric is appropriate for the observed class balance, and writes JSON and HTML audit reports. The Docker path executes supported notebooks twice in fresh containers and compares normalized metrics, notebook outputs, and environment fingerprints.

## Current scope

- Python 3.11+
- Jupyter notebook files (`.ipynb`)
- Local CSV data
- Binary classification
- Metric-suitability check
- Runtime entity-overlap check for supported splits
- Runtime preprocessing-fit-scope check for supported transformers
- Local execution with no paid services or model API
- Optional execution in a restricted Docker container

## Run the example

```bash
PYTHONPATH=src python3 -m validityci audit examples/imbalanced_churn.ipynb \
  --data examples/customer_churn.csv \
  --config examples/validityci.toml \
  --output build/example-audit.json \
  --html build/example-audit.html
```

This direct command has no third-party installation step. Once packaging tools are available, an editable install is optional:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
validityci --help
```

The example intentionally declares `accuracy` as its primary metric for an imbalanced target. ValidityCI should produce a warning with the class distribution and the notebook cell in which accuracy is referenced.

## Execute the example in Docker

Build the pinned runner environment once:

```bash
docker build -f docker/runner/Dockerfile -t validityci-runner:0.4.2 .
```

Then opt in to execution:

```bash
PYTHONPATH=src python3 -m validityci audit examples/runtime_instrumentation.ipynb \
  --data examples/customer_churn.csv \
  --config examples/validityci.toml \
  --execute \
  --output build/executed-audit.json \
  --html build/executed-audit.html
```

`--execute` performs two fresh runs by default. Use `--runs 1` when only execution diagnostics are needed and reproducibility comparison is intentionally out of scope.

The runner stages only the declared notebook and data files. The container has no network, a read-only root filesystem, no Linux capabilities, no privilege escalation, a non-root user, and explicit CPU, memory, process, output, and time limits. Docker itself is a prerequisite; ValidityCI does not silently fall back to host execution.

The initial image supports Python notebooks using pandas and scikit-learn. Notebooks that require other packages are reported as execution failures; arbitrary dependency installation and network access are intentionally unsupported.

For supported scikit-learn metrics, an execution record includes the metric name, value, original notebook cell, sample count, capture method, and safe scalar parameters. Binary label metrics also include aggregate `TN`, `FP`, `FN`, and `TP` counts relative to the configured positive class; target and prediction arrays are never serialized. Continuous-score, multiclass, or otherwise unsupported inputs retain an explicit reason. An optional `primary_metric_variable` in the experiment manifest provides a fallback for custom metric code. If neither a supported call nor a finite fallback variable can be observed, the metric is reported as `unsupported` rather than inferred.

Each successful run also records an aggregate environment fingerprint derived from the Python runtime, operating system, machine architecture, runner code, and installed package names and versions. Reports preserve the three comparison signals separately: equal metrics do not hide changed notebook outputs, and equal outputs do not hide an environment change.

The `0.4.2` runner includes a separately versioned runtime trace for supported scikit-learn train/test splits, estimator and transformer fitting, transformations, predictions, and metric calls. Every event points to the original notebook cell and includes only operation metadata, shapes, object classification, and run-scoped HMAC fingerprints. Raw data values and the fingerprint key are never written to the execution result.

When `entity_column` is configured and that column or named series is passed to `train_test_split`, the runner computes aggregate train/test entity overlap inside the kernel. A confirmed overlap produces a blocking, high-confidence finding; reports contain only unique counts, overlap count, and overlap rate—not entity values or entity-level hashes.

The preprocessing-fit-scope check compares supported transformer fits with earlier split lineage. Fitting before a split, on the full pre-split dataset, or on the held-out test partition produces a blocking, high-confidence finding; ambiguous or missing lineage is reported as `review` or `unsupported`, never silently passed.

## Run the tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Product boundary

ValidityCI is not intended to be another AI code reviewer. The long-term product is an independent validation gate with controlled execution, locked evaluation policies, deterministic evidence, and an AI investigator that may explain or prioritize verified findings but cannot invent them.

See the [complete project plan](docs/project-plan.md) for the product thesis, audience, architecture, security model, release gates, AI-agent design, evaluation program, risks, and ordered implementation backlog. The shorter [iteration-one roadmap](docs/iteration-one.md) remains as a milestone summary.

The [documentation index](docs/README.md) links the complete project material. Start with the [project workflow](docs/workflow.md) for the current end-to-end system and component responsibilities. The [engineering notes](docs/engineering-notes/README.md) preserve observed hurdles, architectural decisions, open assumptions, anticipated failure modes, and honest project talking points; coding assistants can use the compact [AI context pack](docs/ai-context/README.md).
