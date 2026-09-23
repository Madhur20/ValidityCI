# Development guide for AI tools

## Before changing code

1. Run `git status --short` and treat every existing modification and untracked file as user work.
2. Read this context pack, then inspect only the source and tests related to the requested change.
3. Search the decision log and hurdles for the relevant subsystem before reversing an established choice.
4. Keep static inspection, execution, deterministic findings, and presentation as separate layers.

## Core commands

Unit tests require no installed project dependencies:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Syntax and whitespace checks:

```bash
python3 -m py_compile docker/runner/execute_notebook.py src/validityci/*.py src/validityci/runner/*.py src/validityci/schemas/*.py
git diff --check
```

Build the pinned runner:

```bash
docker build -f docker/runner/Dockerfile -t validityci-runner:0.6.0 .
```

Exercise every supported runtime event:

```bash
PYTHONPATH=src python3 -m validityci audit examples/runtime_instrumentation.ipynb \
  --data examples/customer_churn.csv \
  --config examples/validityci.toml \
  --execute --runs 2 \
  --output /tmp/validityci-runtime.json \
  --html /tmp/validityci-runtime.html
```

Exercise fold-level lineage:

```bash
PYTHONPATH=src python3 -m validityci audit examples/cross_validation.ipynb \
  --data examples/customer_churn.csv \
  --config examples/validityci.toml \
  --execute --runs 1 \
  --output /tmp/validityci-cross-validation.json \
  --html /tmp/validityci-cross-validation.html
```

Exercise the group-isolated counterfactual:

```bash
PYTHONPATH=src python3 -m validityci audit examples/entity_overlap.ipynb \
  --data examples/entity_overlap.csv \
  --config examples/validityci.toml \
  --execute --runs 1 --group-counterfactual \
  --output /tmp/validityci-counterfactual.json \
  --html /tmp/validityci-counterfactual.html
```

Use explicit `/tmp` paths for smoke-test reports so existing ignored files under `build/` are not overwritten.

## Test map

| Test file | Covers |
|---|---|
| `tests/test_audit.py` | Configuration, static audit, report invariants, evidence references, and JSON/HTML basics. |
| `tests/test_runner.py` | Execution schemas, fake runner behavior, orchestration statuses, metrics, and execution reporting. |
| `tests/test_docker_runner.py` | Input staging, Docker security flags, timeout cleanup, and structured host-side errors. |
| `tests/test_entity_overlap.py` | Holdout and cross-validation entity-overlap outcomes, privacy-minimized evidence, unsupported behavior, and check-result contracts. |
| `tests/test_confusion_matrix.py` | Confusion-matrix schema invariants, round trips, unsupported states, and absence of target/prediction arrays. |
| `tests/test_counterfactual.py` | Counterfactual lineage, transformation requirements, single-metric boundary, signed delta, and schema invariants. |
| `tests/test_preprocessing_order.py` | Holdout and per-fold transformer fit scope, parallel-CV abstention, ambiguous lineage, repeated executions, and privacy-minimized evidence. |
| `tests/test_policy.py` | Complete policy catalog, expected severity/confidence mappings, stable IDs, and unknown-outcome rejection. |
| `tests/test_reproducibility.py` | Metric/output/environment comparison and audit findings for divergence. |
| `tests/test_runtime_instrumentation.py` | Trace versions, event ordering, fold metadata, privacy fields, and JSON round trips. |

Unit tests do not prove the injected code works against the pinned packages; rebuild the image and run the instrumentation benchmark after changing container instrumentation or its schema.

## Change checklist

- Add or update immutable schema models before changing producers or consumers.
- Update container and host schema versions together when execution JSON changes.
- Add a fake-runner/unit regression for orchestration behavior.
- Add or update a live benchmark for instrumentation behavior.
- Verify failures remain `incomplete` and unsupported work never becomes pass.
- Verify user source and normalized user outputs remain unchanged by instrumentation.
- Verify no raw rows, secrets, full package inventories, or HMAC keys enter reports.
- Update `docs/workflow.md` if component responsibilities or control flow changed.
- Update this context pack and at least one engineering note for an architectural decision or observed hurdle.

## Documentation ownership

- `docs/workflow.md`: current operational behavior and main components.
- `docs/ai-context/`: compact, current implementation context for coding tools.
- `docs/engineering-notes/`: durable rationale, observations, and assumptions; do not rewrite history into a clean summary.
- `docs/project-plan.md`: product direction and gated backlog, including unimplemented design.
- `README.md`: first-run user instructions and concise public boundary.
