# Decision log

## D-001 — Build an external validation gate, not another AI code reviewer

AI-generated code can look reasonable while still using a leaky split, an unsuitable metric, or an invalid evaluation design. ValidityCI sits outside the code-generation loop and produces evidence from controlled execution. An eventual AI investigator may explain verified evidence, but it should not be the source of truth.

**Tradeoff:** This is harder than generating review comments because it requires execution, instrumentation, and evaluation infrastructure. It also creates a more defensible product boundary.

## D-002 — Deterministic checks come before an AI agent

The project starts with schemas, execution, evidence, and testable checks. Agent work is intentionally deferred until a deterministic baseline and benchmark exist.

**Tradeoff:** The repository accumulates fewer fashionable AI features early, but future agent claims can be measured against something reliable. It also prevents hallucinated findings from being presented as validation evidence.

## D-003 — Use explicit, versioned contracts

Audit reports and execution messages have independent schema versions. Models are immutable, reject unknown fields, validate identifiers and references, and support JSON round trips.

**Tradeoff:** Schema changes take more work, but report consumers and future remote runners get a stable integration boundary.

## D-004 — Never silently fall back from Docker to host execution

If the image, daemon, or permissions are unavailable, the audit becomes `incomplete`. Running arbitrary notebook code directly on the host would violate the central safety claim.

**Tradeoff:** Some users will encounter setup friction. That friction is preferable to surprising code execution with access to credentials and local files.

## D-005 — Stage declared files instead of mounting the project directory

The runner resolves and copies only the notebook and data paths listed in the request. The original directories, `.env` files, Git configuration, SSH material, and unrelated datasets are not mounted.

**Tradeoff:** Notebooks with undeclared local dependencies fail. That is intentional for the initial contract and may later be addressed with an explicit project manifest rather than a broad mount.

## D-006 — Treat network denial as a fixed policy for the restricted runner

Although the request schema carries a network flag, this implementation rejects requests that enable it. Supporting network access safely requires destination policies, credential handling, and stronger exfiltration controls.

**Tradeoff:** Notebooks that download data or models cannot run. Reproducible validation should prefer declared, versioned inputs.

## D-007 — Use a narrow initial environment

The first image supports Python 3.11, Jupyter execution, pandas, and scikit-learn. PyTorch, TensorFlow, Spark, system packages, GPUs, and arbitrary installation are deferred.

**Tradeoff:** Compatibility is limited, but the image is understandable and the first benchmark can be made meaningful. User-provided images may be considered later, with an explicit reduction in assurance.

## D-008 — Preserve evidence even when a later phase fails

Static checks still run when container execution fails, but the overall status becomes `incomplete`. The report can therefore show a supported warning without pretending the entire audit completed.

**Tradeoff:** Reports need phase-aware interpretation. The alternative—discarding valid partial evidence—would make diagnosis harder.

## D-009 — Instrument the kernel with hidden cells, not rewritten user code

Metric wrappers must exist before the notebook imports scikit-learn functions, and the wrapper needs the original cell index at call time. The runner creates an in-memory execution notebook containing a setup cell, a small marker cell before each user code cell, and a final collector cell. These synthetic cells are removed before fingerprinting.

**Tradeoff:** Execution counts inside the temporary kernel include synthetic cells. They are excluded from normalized fingerprints. In return, original source is untouched, future imports and magics keep their placement, reported cell indexes refer to the source notebook, and instrumentation output does not affect the user-output fingerprint.

## D-010 — Prefer observed calls, with one explicit fallback

Supported scikit-learn function calls are stronger evidence because they provide the operation, value, cell, and sample count. Some custom code produces the primary metric without calling a supported function, so the manifest may name one Python variable as a fallback. Arbitrary expressions are not evaluated.

**Tradeoff:** A variable selector has weaker provenance and no reliable originating cell or sample count. Reports preserve that distinction through `capture_method` instead of presenting both sources as equivalent.

## D-011 — Repeat in fresh containers, not the same kernel

Reusing a kernel would preserve imports, caches, global variables, random-generator state, and mutated dataframes from the first run. Each execution receives a new staging directory, container name, process tree, and kernel. The declared inputs and resource policy remain the same.

**Tradeoff:** Two runs roughly double execution cost. The CLI therefore defaults to two only when container execution is requested and supports `--runs 1` for diagnostic use.

## D-012 — Keep metric, output, and environment comparisons separate

A stable primary metric can coexist with changed logs or secondary outputs. Matching outputs can also come from different software environments. The comparison stores all three signals instead of collapsing them before reporting.

**Tradeoff:** Reviewers receive a slightly richer result, but they can distinguish result instability from environment drift and decide which difference matters.

## D-013 — Use a strict absolute tolerance for the first metric comparison

Floating-point values are compared with zero relative tolerance and an absolute tolerance of `1e-12`. Exact equality would overreact to insignificant representation noise, while a broad relative tolerance could hide meaningful changes in small metrics.

**Tradeoff:** One fixed tolerance will not suit every metric or domain. A future policy layer should allow reviewed, metric-specific tolerances rather than silently changing the default.

## D-014 — Give runtime traces an independent version

Split, fit, transform, predict, and metric events form a contract that will evolve at a different rate from execution orchestration and audit reports. The runtime trace therefore starts at schema `1.0.0` inside execution schema `1.3.0`, with ordered event IDs and strict round-trip validation.

**Tradeoff:** Consumers must understand three related versions: report, execution, and instrumentation. In return, adding lineage fields or operation adapters does not make the meaning of older traces ambiguous.

## D-015 — Use run-scoped keyed fingerprints for data lineage

The runner generates a fresh 256-bit key inside each notebook kernel and uses HMAC-SHA-256 over canonical type, shape, dtype, index, and value hashes. The key is never emitted. Fingerprints can therefore connect a split output to a later transformer or estimator input within one execution without storing rows or creating a stable cross-run identifier.

**Tradeoff:** Runtime data fingerprints cannot be directly compared between repeated executions. That deliberately gives up cross-run correlation to reduce dictionary attacks against low-cardinality data. Reproducibility continues to compare metrics, normalized outputs, and environments; a future reviewed policy may introduce a stable customer-controlled scope when cross-run lineage is required.
