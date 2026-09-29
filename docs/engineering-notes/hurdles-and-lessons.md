# Hurdles and lessons

## H-001 — Static inspection could be mistaken for independent validation

**Type:** Design decision

The first vertical slice could inspect a notebook and detect that accuracy was a poor primary metric for an imbalanced target. That was useful, but it did not reproduce the experiment. Calling it full validation would have overstated the product.

The code and documentation therefore keep static inspection separate from execution. Container execution is opt-in through `--execute`, and the report includes an execution record only when a runner was used.

**Lesson:** A narrow capability can still be valuable if its boundary is explicit. The important product transition is from reviewing what the notebook says to independently observing what it does.

## H-002 — Execution failure is not a failed experiment

**Type:** Design decision

A timeout, missing dependency, or unavailable Docker daemon does not prove that an experiment is invalid. It only means ValidityCI could not finish evaluating it. Treating both cases as `failed` would give reviewers the wrong signal.

The report model uses `incomplete` for execution problems, `attention_required` for supported checks with findings, and `passed_supported_checks` only when every supported check completed without a finding.

**Lesson:** Status semantics are part of correctness. Infrastructure errors and scientific findings must remain distinguishable in APIs, reports, and CI checks.

## H-003 — The runner needed to be designed before Docker

**Type:** Design decision

Tying orchestration directly to Docker would have made failure handling difficult to test and would have made a future Kubernetes or customer-hosted runner expensive to add. A versioned request/result contract and a small runner protocol were introduced first. A deterministic fake runner covers success, cell failure, timeout, identifier mismatch, and differing outputs.

**Lesson:** The protocol is the stable product boundary; Docker is one implementation. This also lets most tests run in milliseconds without requiring a daemon.

## H-004 — Docker was installed but initially inaccessible

**Type:** Observed

The Docker client was present and Docker Desktop was running, but the development sandbox could not initially access the Docker socket. After socket access was granted, Buildx still failed because it could not update its activity metadata under the local Docker configuration directory.

The permissions were expanded only to the Docker socket and Buildx metadata directory. The runner itself converts Docker launch failures into a structured `runner_error`, so a missing or inaccessible daemon produces an `incomplete` audit rather than a host execution fallback.

**Verification:** The CLI generated an incomplete JSON and HTML report with a container error while the daemon was inaccessible. The same command succeeded after the required local Docker access was granted.

**Lesson:** “Docker is installed” and “the application can use Docker” are separate deployment checks. Failure behavior matters as much as the happy path.

## H-005 — `nbclient` did not imply a usable Python kernel

**Type:** Observed

The first real image build contained `nbclient` and `nbformat`, but the live notebook run returned `NoSuchKernel: No such kernel named python3`. Notebook execution libraries can control a kernel without necessarily installing one.

The image now installs a pinned `ipykernel` runtime explicitly. The image was rebuilt and the example executed successfully.

**Verification:** The first real audit returned `incomplete` with `notebook_execution_error`. After the image change, it returned `succeeded` and a SHA-256 output fingerprint.

**Lesson:** Dependency presence is not the same as end-to-end runtime readiness. A real smoke test caught something unit tests around the Docker command could not.

## H-006 — A non-root container changes bind-mount permissions

**Type:** Observed during implementation review

The initial staging code created an input directory readable only by the host user and input files with owner-only permissions. That is incompatible with the container’s separate non-root UID on Linux. The output directory could also be affected by the host process umask.

Staged files are now read-only but world-readable (`0444`), the input directory is traversable (`0755`), and the dedicated output directory is explicitly writable by the isolated container (`0777`). Only that temporary output directory is writable; the input mount and container root remain read-only.

**Verification:** The non-root image executed the example and wrote its result through the output mount. A separate notebook confirmed that it could not create a file in the input mount.

**Lesson:** “Run as non-root” is not a single flag. Host ownership, bind mounts, umask, and container UIDs have to be considered together.

## H-007 — Killing the Docker client does not guarantee container cleanup

**Type:** Design decision

A host-side subprocess timeout can terminate the `docker run` client while leaving the container running. That would waste resources and allow untrusted code to continue after ValidityCI reported a timeout.

Every execution receives a unique, sanitized container name. On timeout, and again during final cleanup, the runner issues a forced removal for that exact container.

**Verification:** A notebook sleeping for 20 seconds was run with a two-second limit. It returned `timed_out` in roughly two seconds, and no ValidityCI container remained afterward.

**Lesson:** Timeouts must terminate the workload, not just the process waiting for it.

## H-008 — Isolation claims needed adversarial tests

**Type:** Observed verification work

Security flags alone did not prove the intended boundary. A purpose-built notebook attempted to read an unstaged host file, read a host-only environment variable, write into the input mount, and connect to an external IP address.

The notebook succeeded only because all four operations were unavailable. Declared files are copied into a temporary staging directory instead of mounting their source directories, and the Docker command forwards only three controlled environment variables.

**Lesson:** Security properties should be tested from the perspective of the untrusted workload. Command-line inspection is useful, but an adversarial smoke test is stronger evidence.

## H-009 — An output fingerprint is not yet a metric artifact

**Type:** Resolved limitation

The runner originally hashed normalized notebook outputs and could show that the included example produced the same output twice, but it could not extract “accuracy = 0.90” as a structured value. Output equality alone was weaker than understanding the operation that produced the value.

The runner now wraps a declared set of scikit-learn metric functions inside the kernel and emits normalized artifacts with a name, value, cell, sample count, capture method, and safe scalar parameters. The example produced `accuracy = 0.9` from cell 1 across 20 samples. Dataset lineage and full metric semantics remain future work.

**Lesson:** Byte-level or JSON-level equality is useful evidence, but it is weaker than understanding the operation that produced the value.

## H-010 — Instrumentation must not rewrite user source

**Type:** Observed during implementation review

The first instrumentation design prepended setup code and a current-cell marker to user code cells. This worked for the example but would make a valid `from __future__ import ...` statement illegal because future imports must remain at the beginning of a module-like cell. Source rewriting could also interfere with magics or source-sensitive code.

The runner now inserts separate hidden setup, cell-marker, and collector cells into an in-memory execution copy. Original cell objects receive their normal outputs, while user source remains unchanged. Synthetic cells are removed before output fingerprinting.

Hidden cells also change Jupyter execution counters. Those counters and transient display identifiers are therefore excluded from fingerprint input; otherwise instrumentation alone could create a false reproducibility difference.

**Verification:** A live notebook beginning with `from __future__ import annotations` executed successfully and produced a metric artifact through the manifest fallback.

**Lesson:** Instrumentation that appears semantically harmless can violate language-level placement rules. Preserving user source is a stronger default than trying to enumerate every special case.

## H-011 — A missing metric should not fail notebook execution

**Type:** Design decision verified in a live test

A notebook can execute successfully even when ValidityCI cannot establish its declared primary metric. Turning that into a runner failure would confuse compatibility with execution correctness; omitting it would create false confidence.

The collector first uses supported runtime calls, then an explicitly named finite variable. If both are absent, it emits an `unsupported` metric artifact with a reason while leaving execution status as `succeeded`. The overall audit becomes `incomplete`, preventing unsupported evidence from appearing as a pass.

**Verification:** A notebook containing only `answer = 42` completed successfully and returned an unsupported accuracy artifact because its configured fallback variable did not exist.

**Lesson:** Unsupported evidence is a first-class result. It must never be silently converted into pass, zero, or execution failure.

## H-012 — “Same result” needed more than one equality check

**Type:** Design decision verified in live tests

Comparing only notebook-output hashes would show that something changed but not whether the declared metric changed. Comparing only the metric could miss unstable predictions, logs, or secondary artifacts. Neither comparison can distinguish runtime drift from code-level nondeterminism.

The reproducibility artifact stores ordered primary-metric values, maximum absolute delta, normalized output equality, and environment equality separately. A supported mismatch creates a finding with reasons; a missing signal produces `incomplete`.

**Verification:** The stable example matched at `accuracy = 0.9` across both runs with equal output and environment hashes. An unseeded notebook produced different metrics and outputs while retaining the same environment hash.

**Lesson:** A comparison should preserve the observations used to reach its conclusion. A single `reproducible: false` flag is difficult to diagnose and easy to misinterpret.

## H-013 — Environment evidence must be useful without becoming an inventory leak

**Type:** Design decision

Full package lists help debugging but can reveal internal dependencies and make every report large. Recording only an image tag is also weak because mutable tags can refer to different images.

The runner hashes a canonical list of installed package names and versions and the runner entrypoint itself, then combines those hashes with Python version, implementation, operating system, and machine architecture. Reports expose the aggregate hashes and basic runtime fields, not the full package list.

This is data minimization, not a cryptographic privacy guarantee. A reviewer who already suspects a small set of package combinations could reproduce candidate hashes.

**Lesson:** Environment equality improves attribution but does not prove semantic equivalence. System libraries, CPU behavior, locale, and external state may still matter and should be added only when justified by benchmark failures.

## H-014 — Multiple calls to the same metric cannot be reduced to the last value

**Type:** Anticipated and covered in tests

Cross-validation, threshold sweeps, and per-split evaluation can call the primary metric several times. Comparing only the final call could hide changed call counts or earlier values.

The comparison preserves metric values in call order. Different counts are divergence; equal-length sequences are compared element by element and report their maximum absolute delta.

**Lesson:** Normalization should remove irrelevant representation differences without discarding meaningful execution structure.

## H-015 — A useful data fingerprint is also a privacy identifier

**Type:** Design decision verified in a live test

An ordinary content hash would avoid writing raw rows but would still permit cross-report correlation and offline guessing for small identifier domains. The instrumentation now creates a random HMAC key inside each execution, emits only an opaque scope ID, and discards the key with the kernel.

**Verification:** The full runtime benchmark linked the training split to scaler input, scaled training output to estimator input, and prediction output to metric input using equal within-run fingerprints. The serialized JSON contained the HMACs and shapes but neither raw values nor the key.

**Lesson:** “No raw data” is not a complete privacy model. Fingerprint scope and key retention determine whether a digest becomes a durable pseudonymous identifier.

## H-016 — High-level transformer calls produce nested events

**Type:** Observed

Scikit-learn's `fit_transform` commonly calls `fit` and `transform` internally. Instrumenting estimator method access therefore records the nested `fit`, nested `transform`, and enclosing `fit_transform` completion. The sequence is deterministic for the pinned benchmark and preserves the actual call structure rather than collapsing it.

**Verification:** The runtime benchmark produced eight ordered events covering split, scaler fit, scaler transform, scaler fit-transform, test transform, estimator fit, prediction, and metric evaluation. All events pointed to the original notebook cell, and the metric remained `1.0`.

**Lesson:** Event ordering currently describes operation completion, not call entry. Downstream checks must use event type, operation, cell, and fingerprint lineage together instead of assuming every adjacent event is a separate user-authored statement.

## H-017 — Row-level fingerprints cannot prove entity isolation

**Type:** Design decision verified in live tests

Whole-frame fingerprints can connect operation inputs and outputs, but they cannot establish whether repeated business entities crossed a row split. Exporting per-entity hashes would enable the check but would also create a sensitive identifier inventory in the report.

The runner now receives the declared entity column, measures set overlap inside the kernel when that entity data is passed to `train_test_split`, and returns only aggregate counts. The clean benchmark reported zero overlaps across 15 training and 5 test entities. The seeded flawed benchmark reported two overlaps, representing 50% of test entities, and produced a blocking high-confidence finding.

**Lesson:** Privacy-preserving validation often requires moving the computation to the data rather than moving pseudonymous records into the report. When the required lineage is absent, explicit `unsupported` is safer than inference.

## H-018 — Reproducible leakage remains invalid

**Type:** Design decision verified in live tests

The intentionally flawed preprocessing benchmark fits `StandardScaler` on the complete feature matrix before calling `train_test_split`. It executed twice with matching metrics, outputs, and environments, so reproducibility alone correctly reported `reproduced`.

The preprocessing check independently classified both the nested scaler `fit` and enclosing `fit_transform` as occurring before the split in both runs. It produced one blocking, high-confidence finding. The clean benchmark fitted the same transformer only on the captured training output and passed. Serialized reports contained operation metadata and run-scoped fingerprints, but no raw data, data-value field, or fingerprint key.

**Lesson:** Stability and validity are independent properties. Runtime lineage can prove a narrow leakage condition without retaining the underlying records, while duplicate nested events should be summarized into one reviewer finding.

## H-019 — A binary test slice may observe only one class

**Type:** Observed in a live benchmark

The first confusion-matrix implementation required exactly two labels across evaluation targets and predictions. The five-row stratified benchmark slice happened to contain only the negative class, so the runner correctly avoided guessing but returned `unsupported` even though the configured binary positive class made the aggregate interpretation unambiguous.

The capture policy now accepts one or two observed labels. If only the configured positive class appears, all negative-side counts are zero; if only a different class appears, all positive-side counts are zero. More than two labels or a two-label set that cannot uniquely match the configured positive class remains unsupported. The live benchmark then produced `TN=5, FP=0, FN=0, TP=0`, totaling its five samples, with no target or prediction arrays in JSON.

**Lesson:** Binary task semantics come from the declared policy as well as the values present in a small evaluation slice. Absence of a class is evidence, not necessarily unsupported instrumentation.

## H-020 — Fold indices are unnecessary once subsets are fingerprinted

**Type:** Design decision verified in live tests

Cross-validation exposes train/test row indices, but serializing those indices would create row-level artifacts and a new privacy surface. The adapter instead uses the pinned scikit-learn `_safe_indexing` behavior inside the kernel, fingerprints each fold subset, and discards the indices after yielding them back to scikit-learn.

The clean `GroupKFold` benchmark emitted two fold events, measured zero entity overlap in each 10/10 partition, and linked every nested `StandardScaler.fit` to the correct training subset. The paired flawed benchmark fitted the scaler before fold generation; entity isolation passed, while preprocessing scope produced a blocking/high policy-backed finding. Neither report contained train/test indices, entity values, raw data, or the fingerprint key.

A third benchmark used `n_jobs=2`. Fold and entity evidence remained available in the parent process, but transformer events occurred in joblib workers and did not return to the kernel event buffer. Fold metadata now records parallel execution, causing preprocessing analysis to return `unsupported` and the overall audit to remain `incomplete` instead of claiming no preprocessing was present.

**Lesson:** Existing privacy-minimized lineage primitives can often be extended by moving derivation into the kernel rather than widening the serialized contract with row identifiers.

## H-021 — Counterfactual execution must not masquerade as reproducibility

**Type:** Design decision verified in a live benchmark

The group-isolated run intentionally changes partitioning, so comparing it as the second reproducibility run would report expected output and metric differences as instability. The orchestrator now keeps observed executions separate, runs the counterfactual as an additional labeled variant, and gives it a dedicated comparison contract.

On the repeated-entity benchmark, the observed row split measured two overlapping entities and accuracy `0.8333333333333334`. The counterfactual applied one supported transformation, measured zero overlap, and produced accuracy `1.0`, for a signed delta of `+0.16666666666666663`. Both executions succeeded in the restricted `0.6.0` image. The report contained no entity IDs, row indices, or fingerprint key.

**Lesson:** A controlled intervention needs its own lineage and interpretation. Reusing execution infrastructure is valuable, but observed-repeat and changed-policy comparisons must remain distinct evidence types.

## H-022 — A useful explanation score can hide unsupported claims

**Type:** Anticipated failure converted into a deterministic benchmark gate

A response can ask excellent reviewer questions while attaching the wrong evidence or overstating what an incomplete audit proves. Collapsing all qualities into one score would allow helpful language to compensate for factual errors.

The initial 13-case benchmark therefore calculates observation recall, evidence-link accuracy, question recall, unresolved-assumption recall, unsupported-claim rate, and overall usefulness separately. Wrong citations, unknown rubric selections, and forbidden claims fail the factual-support gate regardless of usefulness. The deterministic baseline passes factual support but intentionally leaves room for better questions and assumption handling.

**Lesson:** Agent evaluation needs non-compensatory correctness gates. Helpfulness should be optimized only among responses that preserve the deterministic evidence boundary.

## H-023 — Metric IDs are not globally unique inside a report

**Type:** Design issue found while defining investigator tools

Every execution numbers metric artifacts from `metric.1`, so repeated and counterfactual runs can contain the same metric ID. A tool accepting only `metric.1` could silently return the wrong execution's value and still appear evidence-linked.

The read-only investigator API therefore requires both execution and metric ID and publishes the canonical supporting reference as `<execution_id>/<metric_id>`. Benchmark fixtures enforce that form for metric evidence.

**Lesson:** Evidence citation systems must respect the true uniqueness scope of every underlying contract; a locally unique identifier is unsafe when flattened into an agent tool namespace.

## H-024 — A provider-neutral interface is insufficient without a provider-independent validator

**Type:** Anticipated integration failure covered by unit tests

A model SDK adapter could return a plausible object containing an invented evidence ID, an undeclared field such as model-selected severity, or no result at all. If each provider validated its own output, behavior would drift and a new provider could silently weaken the evidence boundary.

The shared investigator runner now validates the exact output shape and every report-scoped citation after the adapter returns. Tests exercise a valid fake response, a hallucinated citation, an unknown field, and a provider exception; every invalid path records the reason and returns the same deterministic fallback.

**Lesson:** Keep correctness enforcement on the trusted side of a replaceable model boundary, and test rejection behavior without requiring a live provider.

## H-025 — Unsupported metric evidence disappeared from the first fallback snapshot

**Type:** Regression found while freezing deterministic investigator output

The first snapshot pass showed that an incomplete report containing an unsupported primary-metric artifact produced no verified observation. The benchmark rubric knew about the qualified metric record, but the fallback summarized findings, checks, failures, reproducibility, and counterfactuals without walking metric artifacts.

The fallback now emits an explicit unsupported observation citing `<execution_id>/<metric_id>`, preserves the missing value as an unresolved assumption, and asks how the metric should be captured. Permanent snapshots cover all six materialized reports, and the adversarial corpus attacks every rubric case.

**Lesson:** Snapshotting abstention paths is valuable because omission can weaken a report without producing an invalid schema or an obvious false claim.

## H-026 — Matching infrastructure failures are not evidence of instrumentation transparency

**Type:** Failure found during the first live differential run

The sandbox initially denied access to the Docker socket. Both paired executions returned the same `container_error`, and the first comparator version classified their matching failure signatures as equivalent. That proved only that both launches failed in the same way; no notebook behavior had been observed.

The comparator now permits failure equivalence only for `cell_failed`, where kind, message, and original cell index must match. Timeouts and runner/container errors fail closed. After Docker access was granted, the full supported-operation notebook produced the same normalized output fingerprint in both modes, and a separate intentional failure preserved `ValueError: differential sentinel` at original cell index 1.

**Lesson:** Differential tests need an admissibility rule for outcomes. Symmetric test-harness failure must not be mistaken for symmetric system behavior.

## H-027 — Iterable folds bypass the base cross-validator hook

**Type:** Compatibility gap verified in the pinned runner

Passing a list of `(train_indices, test_indices)` pairs to `cross_val_score` does not use the ordinary base implementation that ValidityCI previously wrapped. Scikit-learn normalizes the list into `_CVIterableWrapper`, whose concrete `split` method yields the pairs directly.

The new adapter routes both implementations through one recorder and labels their provenance as `base_cross_validator` or `iterable`. In the live two-fold benchmark, both entity-overlap and preprocessing-scope checks passed, all transformer fits matched their fold-training subset, the report contained no indices, and the instrumented/reference output fingerprints matched.

**Lesson:** Interface inheritance does not guarantee calls pass through a base-method hook. Pinned private adapters need focused live benchmarks and explicit versioning.
