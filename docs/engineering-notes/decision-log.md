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

## D-016 — Compute entity overlap inside the kernel and export only aggregates

The configured entity column is passed to the runner as policy context. When the column or a named entity series participates in `train_test_split`, instrumentation computes train/test unique counts and their intersection inside the temporary kernel. Only counts and the test-overlap rate enter the trace; entity values and entity-level hashes do not.

**Tradeoff:** ValidityCI cannot measure overlap when a notebook drops the entity before splitting or uses an unsupported splitter. That case is reported as `unsupported` and makes the requested audit incomplete instead of guessing from row fingerprints or silently passing.

## D-017 — Classify preprocessing scope from completed runtime lineage

Supported scikit-learn method events now identify whether the object is a transformer or estimator. The check examines transformer `fit` and `fit_transform` completion events, then compares their input fingerprints with earlier `train_test_split` inputs and train/test outputs. A fit before the split, on the full input, or on the test output is blocking; unmatched lineage requires review.

**Tradeoff:** Completion ordering and fingerprint equality provide strong evidence for the pinned adapter but do not model arbitrary pipelines, custom transformers, cross-validation, or transformations that create a derived training view before fitting. Missing object classification or split lineage is therefore `unsupported`, and an unmatched derived input is `review`, rather than inferred as safe or leaky.

## D-018 — Export confusion counts, not classification arrays

Supported metric wrappers compute binary `TN`, `FP`, `FN`, and `TP` counts inside the notebook kernel using the manifest's positive class. Only those four counts and the already-declared positive-class value enter the metric artifact. Runtime target and prediction arrays remain inputs to the existing run-scoped fingerprinting path and are not serialized.

**Tradeoff:** Aggregate counts enable class-sensitive review without creating a row-level prediction artifact, but they cannot support threshold analysis, subgroup slicing, or error inspection after execution. Continuous-score, multiclass, ambiguous-label, and manifest-variable cases therefore retain an explicit unsupported reason until a separately reviewed evidence contract exists.

## D-019 — Version finding impact as policy

Severity and confidence are reviewer-impact decisions, not incidental presentation fields. A central catalog now maps each supported check/outcome pair to a stable policy ID, version, severity, confidence, and rationale. Finding producers resolve that catalog rather than choosing enum values locally, and serialized findings retain policy provenance.

**Tradeoff:** Adding a new finding outcome now requires an explicit policy entry and regression expectation before code can emit it. This adds deliberate friction, but prevents different checks—or future AI-generated explanations—from silently assigning inconsistent blocking levels to similar evidence.

## D-020 — Represent cross-validation as ordinary fold-level split events

Supported scikit-learn splitters eventually flow through `BaseCrossValidator.split`. The runner wraps that generator, applies scikit-learn's own safe indexing to reconstruct each yielded train/test subset, and emits the existing split-event contract with `split_kind=cross_validation` and a one-based fold index. Existing entity and preprocessing checks can therefore evaluate every fold without a parallel evidence model.

**Tradeoff:** Reconstructing fold subsets adds hashing work proportional to the number of folds, but avoids exporting row indices and keeps lineage comparable with holdout splits. This initial decision left iterable CV and splitters bypassing `BaseCrossValidator.split` unsupported; D-026 later added the pinned iterable wrapper while arbitrary custom classes remain outside coverage.

## D-021 — Make counterfactuals explicit execution variants

A group-isolated counterfactual is one additional restricted execution whose request and result are labeled `group_isolated_counterfactual`. During that run only, the kernel wrapper replaces supported `train_test_split` calls with `GroupShuffleSplit`, safe-indexes every positional input, and records that the transformation was applied. The observed runs remain unchanged and are the only inputs to reproducibility comparison.

**Tradeoff:** The initial comparison accepts exactly one captured primary-metric call and only the supported holdout adapter. This deliberately abstains on custom splits, cross-validation, or ambiguous metric selection, but prevents an intervention from being confused with an observed repetition and preserves the source notebook unchanged.

## D-022 — Gate investigator work on factual support before usefulness

The investigator benchmark scores expected observations and their supporting record IDs separately from reviewer questions and unresolved assumptions. The deterministic baseline includes report-derived observations but no added analysis. A future investigator must improve the usefulness score while retaining exact evidence links, zero unsupported selections, and no forbidden overclaims.

**Tradeoff:** The first evaluator uses semantic rubric IDs rather than judging free-form prose. That makes the correctness gate deterministic and cheap, but later evaluation still needs a reviewed mapping from generated text to rubric concepts plus human measurement of clarity and reviewer time.

## D-023 — Keep investigator access read-only and qualify local artifact IDs

The investigator context exposes explicit retrieval methods over an immutable `AuditReport`; it cannot alter findings, policy impact, or status. Returned values are serialized copies. Evidence, check, and execution IDs are already report-scoped, but metric IDs repeat in each execution, so investigator references use `<execution_id>/<metric_id>`.

**Tradeoff:** Qualified IDs and narrow methods are more verbose than handing a model the entire report. They remove ambiguity, reduce accidental data exposure, and make every supported observation mechanically auditable.

## D-024 — Validate provider output outside the model adapter and fail to a deterministic summary

The investigator adapter has one provider-neutral operation: generate a structured draft from the read-only context. Core code—not provider code—then enforces the exact response fields, unique observation and citation identifiers, non-empty text, and membership of every citation in the current report's supporting-record set. Provider exceptions and invalid drafts return the deterministic evidence-linked summary with a rejection reason.

**Tradeoff:** A strict boundary rejects potentially useful extra fields and does not attempt to repair malformed output. This keeps provider behavior replaceable and prevents permissive parsing from turning unsupported model text into accepted audit conclusions.

## D-025 — Verify instrumentation against a reference run inside the same sandbox

The runner entry point has an explicit reference mode that skips hidden setup, cell markers, wrappers, and the collector while retaining the same image, staged inputs, network denial, resource limits, and output normalization. The production runner defaults to instrumentation enabled; reference mode exists for differential verification and is never an automatic audit fallback.

The comparator accepts either identical normalized user-output fingerprints after two successful runs or the same user-cell failure kind, message, and original cell index. It ignores duration but rejects timeouts, runner errors, missing instrumented traces, and unexpectedly instrumented references.

**Tradeoff:** Each live differential case doubles container work and cannot prove transparency for unsupported libraries or nondeterministic notebooks. It directly tests the supported wrapper surface without weakening isolation or conflating infrastructure failure with behavioral equivalence.

## D-026 — Adapt pinned iterable cross-validation at its concrete wrapper

Scikit-learn converts an explicit iterable of train/test index pairs into its internal `_CVIterableWrapper`. That class implements `split` directly and bypasses the existing `BaseCrossValidator.split` hook, so ValidityCI now wraps both paths through one fold-recording function and records `cv_adapter` provenance.

Each yielded pair is safe-indexed inside the kernel to create the same privacy-minimized fold lineage used by built-in splitters. The raw indices are immediately yielded back to scikit-learn and never enter the runtime trace. Instrumentation schema `1.6.0` identifies this expanded semantic surface.

**Tradeoff:** `_CVIterableWrapper` is a private API, but the runner pins scikit-learn `1.6.1` and now has a live compatibility benchmark. Arbitrary custom splitter classes that bypass both supported hooks remain unsupported rather than inferred.
