# Differential instrumentation benchmark

This benchmark checks whether hidden runtime instrumentation changes behavior visible from the original notebook cells. Both executions use fresh containers, the same pinned image and staged inputs, and the same restricted Docker policy.

The instrumented run injects the normal setup, original-cell markers, wrappers, and collector. The reference run disables all injection. A comparison passes only when:

- both runs succeed with the same normalized user-output fingerprint; or
- both runs fail in user code with the same failure kind, message, and original cell index.

Matching timeouts, runner errors, or container errors do not establish equivalence. Duration is intentionally not compared, and reference mode is never used as an audit fallback.

After building `validityci-runner:0.6.0`, run the supported-operation benchmark:

```bash
PYTHONPATH=src python3 benchmarks/differential/run.py \
  examples/runtime_instrumentation.ipynb \
  --data examples/customer_churn.csv \
  --metric-name accuracy --metric-variable accuracy \
  --entity-column customer_id --positive-class 1
```

Run the failure-equivalence benchmark:

```bash
PYTHONPATH=src python3 benchmarks/differential/run.py \
  benchmarks/differential/cell_failure.ipynb \
  --data examples/customer_churn.csv \
  --metric-name accuracy
```

Both commands exit successfully only when the comparison passes. The harness prints execution metadata and privacy-minimized instrumentation evidence, but does not write raw notebook outputs or dataset rows.
