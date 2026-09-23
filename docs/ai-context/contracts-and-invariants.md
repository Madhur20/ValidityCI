# Contracts and invariants

## Versioning

Report, execution, and runtime instrumentation contracts have independent semantic versions. Any serialized shape or meaning change requires the appropriate version bump in both the host schema and container emitter, plus round-trip and rejection tests.

Unknown fields and unknown versions are rejected. Models are frozen and slotted, nested mappings are made immutable, identifiers are unique where required, and findings may reference only evidence present in the same report.

## Status semantics

- `passed_supported_checks`: all requested supported work completed with no finding.
- `attention_required`: at least one supported finding exists, including supported reproducibility divergence.
- `incomplete`: execution failed, primary-metric capture is unsupported, or a required comparison signal is missing.

Never use execution failure as evidence that an experiment is methodologically invalid. Never treat unsupported or skipped evidence as pass.

## Execution invariants

- Docker execution is explicit and never falls back to the host.
- Only declared files are copied into a temporary input directory; source directories are not mounted.
- Each repeated run receives a new staging directory, container, process, and kernel.
- Network remains disabled, inputs and root are read-only, and only the dedicated temporary output mount is writable.
- A host wall timeout forcibly removes the named container; a cell timeout remains a structured notebook result.
- Container output is size-bounded before parsing and must match the requested execution ID.

## Instrumentation invariants

- Original user cell source is not changed.
- Runtime events are contiguous, ordered from one, and link to an original cell.
- Every serialized event contains at least one supported input or output data fingerprint.
- Metric artifacts remain separate from runtime metric events because they serve different consumers.
- Manifest-variable metrics have weaker provenance and must retain a distinct capture method.
- Synthetic cells and transient execution metadata do not affect the normalized notebook-output fingerprint.

## Privacy invariants

- Raw dataset rows and full notebook outputs are not serialized into reports.
- Runtime data fingerprints use HMAC-SHA-256 with a new random key for every execution.
- The key is not emitted; only an opaque scope ID, type, dimensions, and digest are returned.
- Do not change fingerprints to stable unsalted hashes without a documented threat model and explicit product decision.
- Package inventories are hashed; reports expose only the aggregate hash and basic platform fields.

## Reproducibility invariants

- Ordered primary-metric calls are compared, not only the final value.
- Metric count changes are divergence.
- Numeric comparison currently uses absolute tolerance `1e-12` and zero relative tolerance.
- Metric, normalized output, and environment comparisons remain separate signals.
- Two matching runs are evidence of stability, not proof of determinism or methodological validity.

## Finding invariants

- Findings originate from deterministic checks over captured evidence.
- Every finding references immutable evidence IDs.
- Severity must reflect evidence strength; heuristic source observations should not become blocking runtime claims.
- Reporting and any future LLM may explain findings but may not create unsupported blocking verdicts.
