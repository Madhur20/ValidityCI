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

**Type:** Known limitation

The runner hashes normalized notebook outputs and can show that the included example produced the same output twice. It does not yet extract “accuracy = 0.90” as a structured metric with its arguments, cell, dataset lineage, and semantic meaning.

The next milestone is runtime metric capture. Until that exists, a matching fingerprint demonstrates output stability, not scientific reproducibility or metric correctness.

**Lesson:** Byte-level or JSON-level equality is useful evidence, but it is weaker than understanding the operation that produced the value.
