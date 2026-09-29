# Ideas and failure modes

Items here are anticipated unless explicitly linked to an observed hurdle. They are useful design prompts and benchmark candidates, not completed features.

## Execution and reproducibility

### Notebook state can exist outside the notebook

A notebook may depend on cells executed out of order, variables left in a long-running kernel, local files, environment variables, shell commands, database connections, or imported modules from a nearby source tree. A clean container will expose these hidden dependencies as failures.

Possible response: classify missing declared inputs separately from code errors, add a manifest for local modules and artifacts, and preserve the principle that dependencies must be explicit.

### Equal output fingerprints can still hide invalid methodology

A leaky experiment may reproduce perfectly. Repeated execution establishes stability, not validity. Reproducibility checks must remain separate from split, preprocessing, and metric checks.

### Different fingerprints may be harmless

Notebook outputs can contain timestamps, randomly assigned object addresses, progress bars, warning order, or display metadata. A raw difference could create false alarms.

Possible response: define output-type-specific normalization, report which cells differ, compare structured metric artifacts separately, and label unsupported output types instead of guessing.

### Seeds are not sufficient for reproducibility

Python, NumPy, scikit-learn, deep-learning libraries, parallel algorithms, GPUs, and external services have separate sources of randomness. Some operations remain non-deterministic even after seeding.

Current response: repeat execution in fresh containers and compare metric, output, and environment fingerprints. Future work still needs seed tracing, controlled parallelism, and repeated statistical trials for intermittent variation.

Two matching runs are evidence, not proof of determinism. A flaky operation can happen to return the same result twice. Policy-driven run counts or statistical checks may be justified for high-risk workflows, but they have direct compute costs.

### A per-cell timeout and a wall timeout solve different problems

A cell timeout identifies the cell that stalled. A wall timeout protects total resources, including kernel startup and cleanup. Both are needed, and the host must remove the actual container when the wall limit expires.

### Output can become a denial-of-service channel

A notebook can print gigabytes, create enormous rich displays, or generate deeply nested JSON. Memory limits help, but serialization and Docker logs are also attack surfaces.

Possible response: disable Docker logs, bound the returned result, truncate individual outputs before hashing, and test decompression bombs and pathological notebook structures.

## Isolation and supply chain

### Docker is a containment layer, not a perfect security boundary

The current controls materially reduce accidental access, but they do not defend against every container-runtime or kernel exploit. Running hostile multi-tenant workloads would require stronger isolation such as dedicated workers, microVMs, sandboxed runtimes, image scanning, and aggressive patching.

### User-provided images weaken comparability

Custom images improve compatibility but let users change dependency versions and potentially the validation environment itself.

Possible response: distinguish trusted ValidityCI images from custom images, sign approved images, capture digests and package inventories, and lower assurance when an unapproved image is used.

### Base tags and transitive packages can move

Pinning direct package versions is better than floating requirements, but complete reproducibility also requires a base-image digest and locked transitive dependencies for each supported architecture.

Possible response: generate a reviewed lock file with hashes, record the image digest in every execution, rebuild on a schedule, and run the benchmark before promoting a new image.

### Secrets can leak through outputs

Not mounting host secrets prevents one class of leak, but declared datasets or user code may still print sensitive values. Reports and future LLM prompts should not automatically include raw notebook output.

Possible response: store aggregates and fingerprints by default, redact known secret patterns, make raw artifact retention explicit, and keep the AI investigator behind a narrow structured-evidence API.

## Runtime evidence

### Metric interception has multiple paths

Metrics may be produced through `sklearn.metrics`, estimator `.score`, custom functions, third-party libraries, or hand-written NumPy expressions. Monkey-patching one public function will miss aliases and imported references.

Current response: the runner instruments six declared scikit-learn functions before notebook imports, accepts one identifier-only manifest variable as a weaker fallback, records the capture method, and returns `unsupported` when neither path establishes the expected metric. Estimator `.score`, custom functions, and third-party libraries remain unsupported.

### Instrumentation can change behavior

Wrapping arrays, dataframes, estimators, or functions may change identity checks, serialization, performance, exception behavior, or dispatch.

Possible response: run instrumented and uninstrumented executions, compare normalized outputs and metrics, and keep a regression benchmark for observer effects.

The first comparison is encouraging but narrow: the example retained the same output fingerprint before and after instrumentation. A larger differential benchmark is still required.

### Dataset lineage without raw data is difficult

To prove entity overlap or preprocessing order, the system needs to know which rows or partitions flowed into an operation without storing sensitive row values.

Current response: supported runtime events use run-scoped HMAC fingerprints. The secret key exists only inside the temporary kernel, so equal data can be linked within one execution without creating a cross-run identifier. Entity overlap is computed separately inside the kernel when the declared entity data participates in a supported split; only aggregate counts leave the kernel. Transformer-fit inputs are compared with same-run split lineage to identify pre-split, full-data, test-data, or train-only fitting. This reduces offline guessing risk but intentionally prevents direct fingerprint comparison between repeated executions. Any future stable customer-controlled scope still needs an explicit threat model.

Supported cross-validation extends the same model: built-in and explicit iterable fold subsets are reconstructed and fingerprinted inside the kernel, while train/test row indices are discarded rather than serialized. Arbitrary custom splitter classes, nested CV, and search APIs still need explicit compatibility benchmarks.

### A metric value lacks meaning without context

`0.90` is not useful evidence unless the report knows the metric, positive class, averaging method, split, sample count, and possibly threshold.

Current response: normalized runtime metric artifacts include the operation, scalar value, cell, sample count, safe parameters, and aggregate binary confusion counts when label-valued inputs can be interpreted against the configured positive class. Target and prediction arrays are not retained. Continuous-score, multiclass, and fallback-variable paths keep an explicit unsupported reason for confusion evidence.

Future response: add reviewed threshold, subgroup, and averaging semantics without turning reports into row-level prediction stores. Missing semantic fields should produce `unsupported` or `review`, never an inferred pass.

## Product ideas

- A customer-hosted runner with a lightweight SaaS control plane for policies, approvals, and audit history.
- A signed validation bundle containing the report, image digest, check versions, input fingerprints, and reviewer decision.
- GitHub checks that distinguish findings from incomplete or unsupported validation.
- Organization policy packs for required splits, metrics, seeds, and acceptable thresholds.
- A baseline comparison view that explains which metric, data, code, environment, or policy changed.
- An exception workflow with owner, reason, expiration, and linked evidence instead of a permanent “ignore” flag.
- A benchmark repository with clean, flawed, ambiguous, malicious, and unsupported notebooks.
- Expand the implemented holdout counterfactual beyond `train_test_split`: custom splitters, cross-validation/search APIs, and explicitly modeled stratification semantics.
- An AI investigator limited to evidence retrieval tools, with every conclusion checked against evidence identifiers.
- A local compatibility scanner that reports undeclared files and imports before starting an expensive container run.
