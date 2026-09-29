# Investigator benchmark

This benchmark is the correctness gate that must exist before ValidityCI adds an AI investigator. It tests whether a structured investigator response is useful without weakening the deterministic report's factual support.

## Catalog

`cases.json` uses benchmark schema `1.0.0` and currently contains 13 cases across clean, flawed, ambiguous, unsupported, failure, and counterfactual categories. Cases reference permanent example notebooks or one of six immutable, schema-valid audit reports under `fixtures/`.

Each case declares:

- expected audit and deterministic check statuses;
- allowed supporting record IDs;
- expected evidence-backed observation concepts;
- useful reviewer questions;
- unresolved assumptions that must remain explicit; and
- forbidden overclaims that would weaken the report.

Supporting IDs may identify an `Evidence`, `ExecutionResult`, `MetricArtifact`, or `CheckResult` record exposed by the future read-only investigator tools. They never authorize access to raw rows or unrestricted notebook state.

## Scoring

`validityci.investigator_benchmark` loads and strictly validates the catalog. Candidate responses select observation, question, assumption, and forbidden-claim rubric IDs; every reported observation must carry the exact expected supporting IDs.

The scorer returns:

- observation recall;
- evidence-link accuracy;
- reviewer-question recall;
- unresolved-assumption recall;
- unsupported-claim rate;
- a usefulness score; and
- a factual-support gate.

The deterministic baseline includes only observations already stated by the report. It intentionally contributes no extra questions or unresolved-assumption analysis. A future investigator must improve usefulness while keeping perfect evidence-link accuracy, zero unsupported claims, and no forbidden overclaims.

For catalog `1.0.0`, the deterministic baseline passes the factual-support gate on all 13 cases, has zero unsupported claims, and scores approximately `0.2991` for mean usefulness. Any future investigator comparison must report results against the same catalog version.

Run the baseline:

```bash
PYTHONPATH=src python3 -m validityci benchmark-investigator \
  --output build/investigator-benchmark.json
```

Pass `--responses candidate-responses.json` to score a complete response set. The command writes per-case and aggregate results and exits unsuccessfully when the factual-support release gate fails.

`adversarial-responses.json` deliberately attacks all 13 cases with wrong citations, unknown selections, or forbidden overclaims. It must fail every per-case factual-support gate. `fallback-snapshots.json` freezes the deterministic summaries for all six materialized audit reports, including incomplete and unsupported results.

Run the negative control:

```bash
PYTHONPATH=src python3 -m validityci benchmark-investigator \
  --responses benchmarks/investigator/adversarial-responses.json \
  --output build/investigator-adversarial.json
```

An exit status of `1` is expected because the release gate rejects the corpus.

## Remaining benchmark work

The permanent adversarial corpus, fallback snapshots, offline fake, strict validator, and rejection path are now covered by automated tests. Before enabling model-backed investigator output:

1. Define a reviewed mapping from free-form generated observations to benchmark rubric concepts.
2. Require an external provider candidate to preserve the factual-support release gate.
3. Record provider, prompt/configuration version, latency, token usage, and cost; factual support remains non-compensatory.

The catalog contains no raw entity values, row indices, predictions, or runtime fingerprint keys.
