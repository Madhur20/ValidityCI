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
