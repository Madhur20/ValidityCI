# AI context pack

This directory is the short onboarding path for an AI coding tool. Read it before exploring the wider repository; consult source files only for the part being changed.

## Recommended reading order

1. [Current state](current-state.md) — what exists, what does not, and what comes next.
2. [Architecture and file map](architecture.md) — control flow and ownership boundaries.
3. [Contracts and invariants](contracts-and-invariants.md) — statuses, versions, security, privacy, and correctness rules.
4. [Development guide](development-guide.md) — commands, test map, and change checklist.
5. [Project workflow](../workflow.md) — detailed end-to-end workflow and component catalog.

For rationale behind a specific decision, search [the decision log](../engineering-notes/decision-log.md). For previously observed problems, search [hurdles and lessons](../engineering-notes/hurdles-and-lessons.md). Do not read the full product plan unless the task concerns roadmap, positioning, releases, or product scope.

## One-paragraph project model

ValidityCI statically inspects a declared tabular-classification notebook and can optionally execute it twice in fresh restricted Docker containers. It produces immutable evidence about the dataset, supported metrics, normalized outputs, runtime environment, reproducibility, and supported data-flow events; deterministic code—not an LLM—determines findings and audit status.

Investigator work is gated by the versioned 13-case benchmark in `benchmarks/investigator/`, which scores factual support separately from added reviewer usefulness. The implemented provider-neutral boundary validates structured output and report-scoped citations, then falls back to a deterministic summary on rejection; no external model is connected.

## Non-negotiable principles

- Evidence before explanation; never invent observations from source appearance alone.
- Never silently execute untrusted notebook code on the host.
- `incomplete` is distinct from a validity finding and must never become pass.
- Preserve user source; instrumentation uses hidden in-memory cells.
- Do not serialize raw dataset rows or the runtime fingerprint key.
- Preserve existing committed and uncommitted work; this repository is frequently developed with a dirty worktree.
- Update the relevant context document and at least one engineering note after a meaningful architectural backlog item.
