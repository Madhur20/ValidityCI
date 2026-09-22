# ValidityCI

ValidityCI is an independent verification layer for machine-learning experiments. It is intended to reproduce an experiment, run deterministic validity checks, and produce an evidence-backed report before a result is approved or delivered.

This repository currently contains the first vertical slice. It does **not** execute notebook code yet. It safely reads a notebook, profiles a local CSV, checks whether the declared primary metric is appropriate for the observed class balance, and writes JSON and HTML audit reports.

## Current scope

- Python 3.11+
- Jupyter notebook files (`.ipynb`)
- Local CSV data
- Binary classification
- Metric-suitability check
- Local execution with no paid services or model API

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

## Run the tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Product boundary

ValidityCI is not intended to be another AI code reviewer. The long-term product is an independent validation gate with controlled execution, locked evaluation policies, deterministic evidence, and an AI investigator that may explain or prioritize verified findings but cannot invent them.

See the [complete project plan](docs/project-plan.md) for the product thesis, audience, architecture, security model, release gates, AI-agent design, evaluation program, risks, and ordered implementation backlog. The shorter [iteration-one roadmap](docs/iteration-one.md) remains as a milestone summary.
