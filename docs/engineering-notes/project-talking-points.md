# Project talking points

## Thirty-second explanation

ValidityCI is an independent validation gate for machine-learning experiments. Instead of reviewing whether notebook code looks reasonable, it executes a declared experiment twice in fresh restricted environments and builds evidence about what actually happened. The current system compares normalized metrics, notebook outputs, and environment fingerprints; it captures privacy-minimized lineage, aggregate confusion counts, and blocking evidence for configured entity overlap or supported preprocessing leakage. The next work is severity-policy refinement and broader regression coverage.

## Why this is not another AI code reviewer

The important failures in ML experiments are often methodological rather than syntactic. Correct-looking code can still evaluate the wrong split, leak entities between train and test, fit preprocessing on all data, or optimize an inappropriate metric. ValidityCI is designed as an external evidence producer. An AI agent is useful later for investigation and explanation, but it should consume verified artifacts instead of inventing findings from source code.

## Strong technical story

1. The project began with one narrow, deterministic check to establish the report and evidence model.
2. Execution contracts were separated from Docker so orchestration could be tested with a fake runner.
3. The Docker backend stages only declared files and has an explicit security policy rather than mounting the repository.
4. A real smoke test found that `nbclient` alone did not provide a Python kernel; adding `ipykernel` fixed the end-to-end runtime.
5. Adversarial notebooks verified that host files, environment variables, writes to input, and external networking were unavailable.
6. Failures remain first-class results: cell errors identify the cell and cause, timeouts remove the workload, and unavailable infrastructure produces `incomplete` rather than a false pass.
7. Normalized metrics feed a two-run comparison that preserves metric, output, and environment signals separately.
8. Metric instrumentation uses hidden execution cells so user source remains unchanged; unsupported capture remains separate from failed execution.
9. Reproducibility keeps metric, output, and environment signals separate, and divergence becomes a normal evidence-backed finding.
10. Runtime traces use a separate schema and run-scoped HMAC fingerprints, so downstream checks can follow data flow without storing rows or exporting the key.
11. Entity overlap is computed beside the data inside the temporary kernel; only counts and rates enter the evidence report.
12. Transformer fit scope is classified from same-run split lineage; confirmed pre-split/full/test fitting is blocking, while ambiguity remains review or unsupported.
13. Binary metric evidence adds `TN`, `FP`, `FN`, and `TP` inside the kernel without exporting target or prediction arrays.

## Useful deep-dive questions

### Why Docker?

It provides a practical first isolation and reproducibility boundary that can run locally and later inside a customer-controlled worker. It is not treated as perfect protection against hostile multi-tenant code. Stronger isolation would be required for that threat model.

### Why copy inputs instead of mounting the repository?

The notebook should see only the assets declared for the audit. A repository mount would expose unrelated datasets, `.env` files, Git configuration, and possibly credentials. Explicit staging also reveals hidden notebook dependencies.

### Why have an `incomplete` status?

A timeout or missing dependency is not evidence that the experiment failed a validity check. Conflating those outcomes would make CI automation misleading and could create false confidence when phases are skipped.

### What does the output fingerprint prove?

It proves that the normalized notebook outputs matched for the tested runs. It does not prove that the methodology was valid, that every environment detail matched, or that the metric was computed from the right data. Those require separate evidence.

### Why both runtime wrappers and a manifest variable?

Runtime wrappers provide stronger provenance: the metric operation, original cell, sample count, and selected parameters. Custom metric code may not call a supported function, so one explicitly named numeric variable is allowed as a fallback. The report records which method was used and returns `unsupported` instead of guessing when neither works; the audit remains `incomplete` until the primary metric is captured.

### Why are two matching runs not proof of determinism?

Intermittent behavior can match by chance, and some nondeterminism affects predictions without changing a rounded primary metric. Two fresh runs are a practical early signal. ValidityCI therefore preserves metric and output comparisons separately and avoids claiming mathematical proof of reproducibility.

### Where will AI appear?

After deterministic evidence and an investigator benchmark exist. The proposed agent will have narrow tools for reading findings, execution records, lineage, and policies. Its output must cite evidence identifiers, and unsupported claims should be rejected or replaced with a deterministic summary.

## Honest current limitations

- The supported execution environment is intentionally limited to Python, pandas, and scikit-learn.
- Deterministic checks currently cover metric suitability for imbalanced binary classification, entity overlap, and preprocessing fit scope for supported splits.
- Runtime capture currently covers six scikit-learn metric functions and aggregate binary confusion counts for label-valued calls; continuous-score confusion evidence, estimator `.score`, custom functions, and third-party metric libraries need explicit support or the manifest fallback.
- Runtime lineage covers scikit-learn `train_test_split` and `BaseEstimator` fit/transform/predict methods. Custom and third-party operations are outside the initial adapter and cannot yet be detected as observed-but-unsupported calls.
- Entity overlap is supported only when the configured entity column or named series is explicitly passed through `train_test_split`; otherwise the check is `unsupported` rather than inferred.
- Output comparison detects a changed normalized output but does not yet localize the first differing cell or value.
- Dependency locking and environment fingerprinting are not complete.
- Docker reduces exposure but is not sufficient isolation for arbitrary hostile multi-tenant workloads.
- No external pilot or willingness-to-pay evidence has been collected yet.

## Demo sequence

1. Run the static audit and show the class distribution, finding, and referenced notebook cell.
2. Run again with `--execute` and show the successful execution record and output fingerprint.
3. Show a notebook with a seeded cell error and the exact cell/cause in the report.
4. Explain why the status becomes `incomplete` for runner failures rather than “passed” or “invalid.”
5. Show the normalized `accuracy = 0.9` artifact, its original cell, and its 20-sample count.
6. Show a seeded stable run marked `reproduced` across metric, output, and environment.
7. Show an unseeded run with its metric delta and reproducibility finding.
8. Show the runtime benchmark's ordered events, clean entity/preprocessing results, and aggregate confusion matrix; then show the entity-overlap and pre-split preprocessing benchmarks with their blocking findings. End with severity-policy refinement and broader regression benchmarks.

## Claims to avoid

Do not say that ValidityCI currently proves an ML model is correct, prevents every kind of leakage, securely runs arbitrary hostile code, supports every notebook, or is already a validated SaaS business. A stronger and more credible statement is that the project has established a controlled execution and evidence foundation for a deliberately narrow set of checks.
