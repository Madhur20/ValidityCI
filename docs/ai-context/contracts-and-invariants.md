# Contracts and invariants

## Versioning

Report, execution, and runtime instrumentation contracts have independent semantic versions. Any serialized shape or meaning change requires the appropriate version bump in both the host schema and container emitter, plus round-trip and rejection tests.

Unknown fields and unknown versions are rejected. Models are frozen and slotted, nested mappings are made immutable, identifiers are unique where required, and findings may reference only evidence present in the same report.

## Status semantics

- `passed_supported_checks`: all requested supported work completed with no finding.
- `attention_required`: at least one supported finding exists, including supported reproducibility divergence.
- `incomplete`: execution failed, primary-metric capture is unsupported, or a required comparison signal is missing.

Never use execution failure as evidence that an experiment is methodologically invalid. Never treat unsupported or skipped evidence as pass.

Deterministic `CheckResult` values use `pass`, `fail`, `review`, `not_applicable`, `unsupported`, or `error`. Pass/fail/review require evidence, fail/review require a corresponding finding, and unsupported/error make the overall audit incomplete.

## Execution invariants

- Docker execution is explicit and never falls back to the host.
- Only declared files are copied into a temporary input directory; source directories are not mounted.
- Each repeated run receives a new staging directory, container, process, and kernel.
- Network remains disabled, inputs and root are read-only, and only the dedicated temporary output mount is writable.
- A host wall timeout forcibly removes the named container; a cell timeout remains a structured notebook result.
- Container output is size-bounded before parsing and must match the requested execution ID.
- Container output must also match the requested execution variant (`observed` or `group_isolated_counterfactual`).

## Instrumentation invariants

- Original user cell source is not changed.
- Runtime events are contiguous, ordered from one, and link to an original cell.
- Supported built-in and explicit iterable cross-validation emits one split event per yielded fold with a one-based fold index and adapter provenance; train/test row indices are never serialized.
- Every serialized event contains at least one supported input or output data fingerprint.
- Supported scikit-learn method events classify the object as a transformer or estimator; missing classification makes preprocessing analysis unsupported.
- Metric artifacts remain separate from runtime metric events because they serve different consumers.
- Manifest-variable metrics have weaker provenance and must retain a distinct capture method.
- Captured confusion matrices contain only four non-negative aggregate counts and the already-declared positive class; target and prediction arrays never enter the execution result.
- One-class evaluation slices may still produce a binary confusion matrix. More than two observed labels, ambiguous positive-class matching, or score-valued predictions are explicitly unsupported.
- Synthetic cells and transient execution metadata do not affect the normalized notebook-output fingerprint.
- Differential verification uses two fresh containers under the same security policy; reference mode disables injection but is not an audit fallback.
- Differential equivalence requires matching successful output fingerprints or matching original-cell failure kind, message, and index. Timeouts and runner errors never establish equivalence.
- A group-isolated counterfactual is a distinct execution variant and never participates in the observed-run reproducibility comparison.

## Privacy invariants

- Raw dataset rows and full notebook outputs are not serialized into reports.
- Entity-overlap reports contain only aggregate unique counts, overlap count, and overlap rate; entity values and entity-level hashes remain inside the kernel.
- Runtime data fingerprints use HMAC-SHA-256 with a new random key for every execution.
- The key is not emitted; only an opaque scope ID, type, dimensions, and digest are returned.
- Do not change fingerprints to stable unsalted hashes without a documented threat model and explicit product decision.
- Package inventories are hashed; reports expose only the aggregate hash and basic platform fields.

## Leakage-check invariants

- Entity overlap is established from in-kernel aggregate measurements, not row fingerprint inference.
- Preprocessing fit scope is established only from supported transformer events and same-execution split lineage.
- Every captured holdout or cross-validation split is evaluated independently; a clean split cannot mask a later violation.
- A transformer fitted before the split, on the full split input, or on the held-out output is a confirmed blocking violation.
- Unmatched fit lineage is `review`; absent required lineage or metadata is `unsupported`. Neither outcome is pass.

## Reproducibility invariants

- Ordered primary-metric calls are compared, not only the final value.
- Metric count changes are divergence.
- Numeric comparison currently uses absolute tolerance `1e-12` and zero relative tolerance.
- Metric, normalized output, and environment comparisons remain separate signals.
- Two matching runs are evidence of stability, not proof of determinism or methodological validity.

## Counterfactual invariants

- Counterfactual execution is opt-in and requires a configured entity column; it never overwrites notebook source.
- The initial adapter transforms only supported `train_test_split` calls and records each applied transformation.
- It preserves an explicit notebook `random_state`; when absent, it uses the manifest's declared random seed so the intervention itself is controlled.
- A completed comparison requires successful observed and group-isolated variants, at least one transformed split, and exactly one captured primary metric in each execution.
- The signed delta is `counterfactual - observed`; an unsupported transformation or ambiguous metric selection makes the comparison and audit `incomplete`.
- Entity values and generated train/test indices remain inside the kernel.

## Finding invariants

- Findings originate from deterministic checks over captured evidence.
- Every finding references immutable evidence IDs.
- Every finding records a stable policy ID and policy version from the deterministic catalog.
- Unknown check/outcome combinations must fail closed instead of receiving an ad hoc severity or confidence.
- Severity must reflect evidence strength; heuristic source observations should not become blocking runtime claims.
- Reporting and any future LLM may explain findings but may not create unsupported blocking verdicts.

## Investigator benchmark invariants

- The benchmark catalog has its own version and contains at least 10 cases spanning clean, flawed, ambiguous, unsupported, failure, and counterfactual behavior.
- Expected observations cite an explicit per-case allowlist of supporting record IDs.
- Factual support and usefulness are scored separately; reviewer questions cannot compensate for incorrect evidence links.
- Any wrong citation, unknown rubric selection, or asserted forbidden claim fails the factual-support gate.
- The deterministic baseline uses only report-derived observations. A future investigator must improve usefulness without increasing unsupported claims.
- Benchmark fixtures and responses must not contain raw rows, entity values, predictions, row indices, or runtime fingerprint keys.
- Investigator retrieval is read-only and returns serialized copies, never mutable report models.
- Metric support references are execution-qualified because metric IDs are unique only within one execution.
- Adapter responses accept only the five documented summary fields; observations require unique IDs and at least one known, report-scoped supporting record ID.
- Model-backed output must fall back to the deterministic summary if structured validation or evidence-reference validation fails.
