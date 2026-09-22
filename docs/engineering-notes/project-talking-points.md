# Project talking points

## Thirty-second explanation

ValidityCI is an independent validation gate for machine-learning experiments. Instead of reviewing whether notebook code looks reasonable, it executes a declared experiment in a restricted environment and builds evidence about what actually happened. The current system supports a pandas and scikit-learn notebook, captures supported metric calls as structured runtime artifacts, detects an unsuitable accuracy metric for an imbalanced binary target, and produces versioned JSON and HTML reports. The next work is repeated-execution comparison, followed by lineage instrumentation and leakage checks.

## Why this is not another AI code reviewer

The important failures in ML experiments are often methodological rather than syntactic. Correct-looking code can still evaluate the wrong split, leak entities between train and test, fit preprocessing on all data, or optimize an inappropriate metric. ValidityCI is designed as an external evidence producer. An AI agent is useful later for investigation and explanation, but it should consume verified artifacts instead of inventing findings from source code.

## Strong technical story

1. The project began with one narrow, deterministic check to establish the report and evidence model.
2. Execution contracts were separated from Docker so orchestration could be tested with a fake runner.
3. The Docker backend stages only declared files and has an explicit security policy rather than mounting the repository.
4. A real smoke test found that `nbclient` alone did not provide a Python kernel; adding `ipykernel` fixed the end-to-end runtime.
5. Adversarial notebooks verified that host files, environment variables, writes to input, and external networking were unavailable.
6. Failures remain first-class results: cell errors identify the cell and cause, timeouts remove the workload, and unavailable infrastructure produces `incomplete` rather than a false pass.
7. Normalized metrics now make a stronger comparison possible, but the project does not claim automated metric reproducibility until the two-run comparison is implemented.
8. Metric instrumentation uses hidden execution cells so user source remains unchanged; unsupported capture remains separate from failed execution.

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

### Where will AI appear?

After deterministic evidence and an investigator benchmark exist. The proposed agent will have narrow tools for reading findings, execution records, lineage, and policies. Its output must cite evidence identifiers, and unsupported claims should be rejected or replaced with a deterministic summary.

## Honest current limitations

- The supported execution environment is intentionally limited to Python, pandas, and scikit-learn.
- There is one deterministic validity check today: metric suitability for imbalanced binary classification.
- Runtime capture currently covers six scikit-learn metric functions; estimator `.score`, custom functions, and third-party metric libraries need explicit support or the manifest fallback.
- Output comparison does not yet explain which cell or value changed.
- Dependency locking and environment fingerprinting are not complete.
- Docker reduces exposure but is not sufficient isolation for arbitrary hostile multi-tenant workloads.
- No external pilot or willingness-to-pay evidence has been collected yet.

## Demo sequence

1. Run the static audit and show the class distribution, finding, and referenced notebook cell.
2. Run again with `--execute` and show the successful execution record and output fingerprint.
3. Show a notebook with a seeded cell error and the exact cell/cause in the report.
4. Explain why the status becomes `incomplete` for runner failures rather than “passed” or “invalid.”
5. Show the normalized `accuracy = 0.9` artifact, its original cell, and its 20-sample count.
6. End with the next milestone: comparing normalized metrics and output fingerprints across fresh executions.

## Claims to avoid

Do not say that ValidityCI currently proves an ML model is correct, prevents every kind of leakage, securely runs arbitrary hostile code, supports every notebook, or is already a validated SaaS business. A stronger and more credible statement is that the project has established a controlled execution and evidence foundation for a deliberately narrow set of checks.
