# ValidityCI project plan

Status: living plan  
Last updated: 2026-09-22

## 1. Executive decision

ValidityCI will be built as a **local-first, independent verification layer for tabular machine-learning experiments**.

It will not begin as a generic notebook reviewer, an MLOps platform, or an AI assistant that comments on code. Existing products already provide many data-integrity and train/test checks, and general coding agents will continue absorbing ordinary review features.

The product hypothesis is narrower:

> A model reviewer should be able to take an experiment created by a human or coding agent, reproduce it in a controlled environment, apply locked validation policies, challenge important assumptions with deterministic tests, and receive an auditable evidence package.

The first technical user is a senior data scientist or ML engineer reviewing tabular classification work. The first commercial hypothesis is an applied-ML consultancy with 5–30 data scientists. Georgia Tech students and research groups are accessible pilot users, but they are not assumed to be the eventual paying market.

Two tracks proceed in parallel:

1. **Portfolio track:** build a rigorous and measurable AI-engineering system.
2. **Product track:** validate whether a specific customer has recurring pain and purchasing intent.

Technical progress can remain valuable if the SaaS hypothesis fails. Commercial investment will not continue without customer evidence.

## 2. Problem definition

ML results can be numerically impressive and technically executable while still being invalid for the intended decision. Causes include:

- entities shared across training and testing partitions;
- future information included in historical features;
- preprocessing fitted using evaluation data;
- repeated tuning against the test set;
- a metric that hides the failure mode that matters;
- an unrepresentative evaluation population;
- results that cannot be recreated from the submitted artifacts;
- undocumented assumptions or exceptions;
- differences between evaluation and deployment conditions.

AI code generation increases experiment throughput, but it does not create an independent trust boundary. An agent that chooses the methodology, writes the implementation, writes its tests, and reviews its own output can reproduce the same mistaken assumption at every stage.

ValidityCI should answer:

> “What result was claimed, can it be independently reproduced, which validation policies did it pass, which assumptions remain unresolved, and what evidence supports every conclusion?”

ValidityCI will not claim that a passing report proves universal correctness, that statistical validity can be inferred without domain context, that an LLM replaces a human validator, or that a generic checklist proves regulatory compliance. The report is decision support and evidence, not certification.

## 3. Target audience

### Initial user

**Senior data scientist or ML engineer reviewing another contributor’s tabular model.**

Their job-to-be-done:

> “Before I approve or deliver this model, help me reproduce the result, identify high-risk methodological assumptions, and assemble the evidence I need to review it efficiently.”

### Initial buyer hypothesis

**Head of Data Science, AI director, CTO, or technical partner at an applied-ML consultancy with 5–30 data scientists.**

Potential economic value:

- fewer senior-review hours per project;
- consistent review quality across teams;
- fewer client-facing corrections;
- repeatable evidence for delivery and handoff;
- a record of risks, decisions, and exceptions.

### Pilot audience

Georgia Tech students, TAs, professors, and research groups can provide realistic notebooks, failure examples, usability feedback, benchmark cases, and initial case studies. They should not be treated as evidence of enterprise willingness to pay.

### Audiences excluded initially

- **Large banks:** real need and budget, but long procurement and established model-risk processes.
- **Healthcare deployment teams:** privacy, clinical validation, and compliance would overwhelm the initial product.
- **Big technology companies:** difficult access and likely internal platforms.
- **Individual hobbyists:** accessible but limited willingness to pay.
- **Deep-learning research teams:** distributed environments expand the execution problem too early.

## 4. Evidence and assumptions

### Confirmed external signals

- NIST recommends repeatable testing, evaluation, verification, validation, and independent review: <https://airc.nist.gov/airmf-resources/airmf/5-sec-core/>.
- Federal Reserve model-risk guidance emphasizes testing, documentation, validation, and separation of responsibilities: <https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm>.
- Deepchecks already provides data-integrity, leakage, drift, and model-evaluation suites: <https://docs.deepchecks.com/stable/tabular/index.html>.
- Giskard already scans models and turns findings into test suites: <https://docs.giskard.ai/en/stable/open_source/scan/scan_tabular/index.html>.
- Modern agent evaluation combines deterministic, model-based, and human layers: <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>.

These validate the general problem. They do not prove demand for ValidityCI.

### Unvalidated assumptions

- Reviewers repeatedly spend enough time recreating experiments to justify a product.
- Existing tools do not produce the evidence and workflow reviewers need.
- Teams will allow a local runner to inspect proprietary code and data.
- A standard report can serve multiple client workflows.
- Reviewers trust automated findings when evidence is inspectable.
- An AI investigator saves time beyond a deterministic report.
- The daily user and budget owner can coordinate adoption.

### Discovery plan

Interview at least 15 people: 5 senior data scientists or reviewers, 5 people at analytics or AI consultancies, 3 ML platform/governance practitioners, and 2 professors or lab leads.

Ask about the last real review rather than hypothetical interest:

1. What artifacts did the author submit?
2. What did the reviewer rerun manually?
3. What was missing or misleading?
4. How long did review take?
5. Which parts required senior judgment?
6. Which tools and checklists were used?
7. What evidence was delivered?
8. What happened the last time a problem escaped review?
9. What code and data may an external tool access?
10. Who owns the budget for improving this process?

### Commercial gate

Continue toward B2B SaaS only if at least 5 interviewees recently performed substantial manual validation, at least 3 describe it as recurring, at least 3 agree to a real pilot, existing tools leave a meaningful workflow gap, and at least one commercial team wants successful validation to become standard practice.

If this fails, keep the project as an open-source AI-engineering system or pivot to the pain revealed in interviews.

## 5. Product principles

1. **Evidence before explanation.** Findings originate from deterministic measurements or execution events.
2. **Independent by design.** Validation policies and protected evaluation assets remain separate from code generation.
3. **Local first.** Code and raw data stay on the user’s machine unless explicitly configured otherwise.
4. **Explicit context beats confident inference.** Ask for target, entity, timestamp, metric, and intended use.
5. **Abstention is a feature.** Unresolved domain questions are surfaced, not converted into verdicts.
6. **Severity reflects evidence.** Runtime-confirmed violations may block; heuristics remain warnings.
7. **Human decisions stay visible.** Approvals and exceptions are first-class records.
8. **Narrow support beats false universality.** Expand through tested adapters.
9. **No AI theater.** Add agents, retrieval, or fine-tuning only when evaluation shows improvement.
10. **Every report is reproducible.** Conclusions link to inputs, policy versions, locations, and execution artifacts.

## 6. User workflow

```text
Author or coding agent produces experiment
                    │
                    ▼
Reviewer selects locked validation policy
                    │
                    ▼
ValidityCI runs in a restricted local container
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
   Reproduction        Deterministic checks
         │                     │
         └──────────┬──────────┘
                    ▼
          Counterfactual tests
                    │
                    ▼
        Evidence-backed report
                    │
                    ▼
 Reviewer approves, rejects, or documents exception
```

The future CI flow replaces the manual invocation with a customer-hosted runner and a GitHub status, while preserving human approval.

## 7. Scope

### Initial contract

- Python 3.11+
- Jupyter notebooks
- Pandas, NumPy, and scikit-learn
- local CSV data
- binary tabular classification
- one notebook and one primary dataset
- recognizable scikit-learn APIs
- CPU-only execution

This scope is inexpensive to run and practical to instrument. PyTorch, TensorFlow, Spark, arbitrary databases, and distributed training are deferred.

Expansion order, driven by pilots: multiclass classification, regression, time series, script-based projects, MLflow integration, PyTorch, and custom organization plugins.

## 8. Release plan

### 0.1 — static foundation — completed

- CLI audit command
- TOML manifest
- notebook parsing and CSV profiling
- structured evidence and findings
- metric/class-imbalance check
- JSON and HTML reports
- example and automated tests

Limitation: notebook code is never executed.

### 0.2 — reproducible runner

Build a Docker-compatible runner with no network, read-only inputs, ephemeral outputs, resource limits, timeouts, notebook execution, cell-level errors, environment capture, normalized metrics, and a second-run comparison.

Exit criteria:

- 8 of 10 supported benchmark notebooks execute successfully;
- failures identify the exact cell and cause;
- intentionally non-deterministic results are detected;
- notebook code cannot access host secrets or arbitrary host files;
- no model API key is mounted inside the container.

### 0.3 — runtime evidence

Trace train/test splitting, transformer fitting, estimator fitting, prediction, and metric calls. Link events to notebook cells and fingerprint data without storing raw values.

Exit criteria:

- trace ordering is stable;
- every supported event links to a cell and data fingerprint;
- instrumentation does not materially change results;
- unsupported operations are reported explicitly.

### 0.4 — high-confidence checks

Implement entity overlap, preprocessing before split, metric suitability with class-level results, reproducibility, and uncontrolled randomness.

Statuses: `pass`, `fail`, `review`, `not_applicable`, `unsupported`, and `error`. Unsupported and error must never appear as pass.

Severity levels:

- **Block:** runtime-confirmed violation of configured policy.
- **Review:** strong evidence exists but domain intent matters.
- **Inform:** useful observation without demonstrated invalidity.

Exit criteria:

- all seeded critical defects are detected;
- no blocking finding appears in clean benchmark notebooks;
- every finding contains evidence IDs and affected cells;
- false positives become permanent regression cases.

### 0.5 — controlled counterfactual

Replace a random row split with a configured group-isolated split, rerun downstream work, and compare metrics and partition properties. Never overwrite the source notebook.

Exit criteria:

- original and corrected results appear together;
- transformation is deterministic and reversible;
- executions have explicit lineage;
- unsupported notebooks receive an explanation.

### 0.6 — AI investigator

The agent extracts experiment intent, selects read-only evidence tools, summarizes findings, identifies missing context, generates reviewer questions, and explains results. It may request a supported counterfactual, but it may not create a blocking verdict.

Exit criteria:

- every generated factual claim cites a valid evidence ID;
- invalid model output falls back to deterministic templates;
- LLM-free operation remains fully useful;
- a comparative study shows improved reviewer time or comprehension;
- explanations do not increase critical false positives.

### 0.7 — pilot and GitHub integration

Add a customer-hosted runner, GitHub status, baseline comparison, policy versions, reviewer decisions, exceptions, and exportable validation packages.

Exit criteria:

- 3 external users complete audits without developer assistance;
- 1 real issue is found in a non-seeded experiment;
- 1 team repeats use on a later change;
- users can independently inspect and challenge the evidence.

### 1.0 — team product — conditional

Only after the commercial gate: team workspace, access control, SSO, audit retention, encrypted artifact storage, organization policy packs, private deployment, billing, and usage controls.

## 9. Architecture

```text
CLI / future GitHub integration
              │
              ▼
       Input contract layer
 manifest ─ notebook ─ data ─ policy
              │
              ▼
       Static inspection layer
              │
              ▼
       Restricted runner API
              │
              ▼
      Runtime instrumentation
              │
              ▼
         Evidence store
              │
       ┌──────┴─────────┐
       ▼                ▼
 Check engine     Counterfactual engine
       │                │
       └──────┬─────────┘
              ▼
          Policy engine
              │
              ▼
     Optional AI investigator
              │
              ▼
      Report and review package
```

Module boundaries:

- `schemas`: versioned serialized contracts;
- `parsing`: notebook and manifest reading, never execution;
- `static_analysis`: source facts and candidate evidence;
- `runner`: container lifecycle and artifact collection;
- `instrumentation`: runtime event capture inside the container;
- `checks`: pure deterministic checks over evidence;
- `counterfactuals`: controlled alternative evaluations;
- `policies`: thresholds, severities, and blocking rules;
- `agent`: optional tool selection and evidence-grounded explanations;
- `reporting`: JSON, HTML, and CI output;
- `adapters`: container, model, tracker, and GitHub integrations.

No check should depend on the CLI, UI, or model provider. The agent consumes the same stable evidence as deterministic reports.

## 10. Core data model

### Experiment specification

Task, target, entity/group keys, prediction timestamp and horizon, intended population, primary metric, error costs, random seed, and expected output.

### Policy

Identifier and version, enabled checks, thresholds, severity mapping, evidence requirements, exceptions, and approval requirements.

### Execution

Immutable ID, source and environment fingerprints, status, resource limits, cell results, artifacts, runtime events, and parent execution for counterfactuals.

### Evidence

Immutable ID, kind, producer/version, execution, notebook cells or code locations, measurements, data fingerprint, confidence, and limitations.

### Finding

Check/policy IDs, severity, evidence references, recommendation, status, reviewer decision, and rationale.

### Validation package

Input fingerprints, policy version, execution references, findings, reviewer decisions, reports, and an integrity hash.

## 11. Technical decisions

States: **decided** means implement now; **provisional** means hide behind an interface; **deferred** means do not choose without a requirement.

| Decision | State | Choice | Reasoning |
|---|---|---|---|
| Product mode | Decided | Local-first | Privacy, zero-cost development, easier pilots |
| Initial ML scope | Decided | Tabular binary scikit-learn | Bounded instrumentation and inexpensive execution |
| Manifest | Decided | Explicit TOML | Standard library support and less domain guessing |
| Source of truth | Decided | Structured evidence | Auditability and deterministic testing |
| Notebook execution | Decided | Container only | Notebooks are untrusted code |
| Container interface | Provisional | Docker-compatible adapter | Docker exists locally; interface prevents lock-in |
| Notebook executor | Provisional | `nbclient` | Smaller surface; evaluate Papermill only if parameterization is needed |
| Local database | Decided | SQLite | Transactional, single-user, no service cost |
| Artifact storage | Decided locally | Content-addressed filesystem | Simple, inspectable, deduplicated |
| Schemas | Provisional | Dataclasses now, Pydantic when dependencies begin | Typed contracts without premature dependency |
| Checks | Decided | Pure functions over evidence | Repeatable and independent of UI/LLM |
| Existing validation tools | Provisional | Optional evidence producers | Reuse mature checks without losing architecture control |
| Agent count | Decided initially | One investigator | Easier evaluation; no multi-agent theater |
| Agent authority | Decided | Explain/request tools, never set blocking verdicts | Maintains policy boundary |
| Model provider | Provisional | Adapter, local model default | Zero-cost operation and measurable provider comparison |
| Retrieval | Deferred | SQLite/full-text first | Current evidence is small and addressable by ID |
| Vector database | Deferred | None | No validated semantic-search or scale requirement |
| Fine-tuning/LoRA | Deferred | Benchmark first | Add only if it improves a measured failure category |
| Workflow engine | Deferred | In-process initially | Avoid Temporal/Celery before long-running scale exists |
| Web interface | Deferred | HTML report first | Core trust loop matters more than accounts |
| Hosted execution | Deferred | Customer-hosted runner likely | Better privacy and compute economics |
| Auto-remediation | Decided against initially | Controlled counterfactuals only | Arbitrary rewrites add safety and validity risk |

## 12. Restricted execution

Defaults:

- no network;
- non-root user;
- read-only source/input mounts;
- writable ephemeral output only;
- CPU, memory, process, output-size, and time limits;
- no host sockets, environment variables, or cloud credentials;
- pinned minimal base image;
- container removal after artifact extraction.

Initially use a pinned image containing the supported scientific stack. Arbitrary package installation stays disabled because it weakens reproducibility and requires network access. Later options include approved environment profiles, lock-file builds in a separate phase, private mirrors, or scanned customer images.

Raw data stays inside the runner. Reports contain aggregates and fingerprints by default. The LLM receives structured summaries, not raw rows or entire notebooks.

## 13. Runtime instrumentation

Inject a bootstrap module that wraps supported scikit-learn and metric entry points. Record event type, sequence, timestamp, notebook cell, callable, input/output types and shapes, non-sensitive arguments, fingerprints, exception status, and instrumentation version.

Use runtime plus static analysis: static analysis locates candidate code; runtime evidence proves which path executed and in what order. Every wrapper must preserve the original contract, verified through differential tests against uninstrumented execution.

## 14. Checks and policies

Every check declares a version, supported patterns, required evidence, deterministic procedure, limitations, default severity, remediation, and positive/negative/ambiguous fixtures.

Initial policy pack: `tabular-classification-basic`.

Deepchecks or another library may produce evidence, but its output must be normalized with tool/version provenance. ValidityCI’s differentiation remains reproduction, orchestration, organization policy, evidence, and review workflow.

## 15. AI investigator

Permitted tools:

- `get_experiment_specification`
- `get_execution_summary`
- `get_notebook_cell`
- `list_runtime_events`
- `get_dataset_profile`
- `list_check_results`
- `get_evidence`
- `request_supported_counterfactual`
- `compare_executions`
- `list_policy_requirements`

Output sections: experiment claim, verified observations, unresolved assumptions, prioritized reviewer questions, recommended next action, and evidence IDs.

Controls:

- validate every evidence ID;
- prevent the model from setting severity or pass/block;
- record model, prompt, tools, and configuration versions;
- require unresolved labels for unknown facts;
- retain a deterministic fallback report;
- test adversarial and incomplete evidence.

Evaluate deterministic report, one-shot summary, and tool-using investigator. Measure factual support, issue recall, unsupported claims, reviewer time, cost, and latency. Keep the agent only if it improves workflow without weakening correctness.

## 16. Evaluation program

Build at least 20 benchmark experiments: clean controls, one-defect notebooks, interacting defects, realistic public examples, consenting pilot notebooks, and unsupported patterns.

Each contains expected check status, evidence location, metric, counterfactual result where deterministic, and ambiguity notes.

Metrics:

- execution success and reproducibility rates;
- precision/recall by check category;
- critical false positives;
- unsupported-pattern detection;
- evidence-link correctness;
- reviewer time to decision;
- agent support rate and unsupported-claim rate;
- counterfactual success;
- repeat pilot usage.

Release gates:

- no known host-secret exposure;
- no block without deterministic evidence;
- benchmark regressions fail tests;
- schema changes are versioned;
- every check has positive, negative, and ambiguous fixtures;
- unsupported patterns are documented.

For pilots, compare reviewers working with and without ValidityCI. Record time, issues found, confidence, and disagreements.

## 17. Testing and observability

### Tests

- Unit: schemas, fingerprints, checks, policies, evidence references, rendering.
- Integration: container execution, instrumentation pipeline, counterfactuals, CLI, model adapter with test doubles.
- Security: network, host files, environment exfiltration, process limits, oversized output, timeouts, malicious metadata, HTML escaping.
- Regression: every real false positive, false negative, execution failure, and agent hallucination becomes a fixture when permitted.

### Observability

Record audit ID, phase durations, runner transitions, resource use, instrumentation counts, check versions, counterfactual lineage, agent tool calls/model/latency/tokens, and report status. Never log raw rows, secrets, or full proprietary code by default.

Begin with structured JSON logs. Add OpenTelemetry when multiple processes require trace correlation.

## 18. User experience

Start with CLI plus a self-contained HTML report. This keeps code local, supports automation, and avoids spending effort on accounts before the trust loop works.

Report hierarchy:

1. Decision status and limitations
2. Claimed versus reproduced result
3. Blocking findings
4. Human-review items
5. Counterfactual comparisons
6. Evidence and affected code
7. Environment and reproducibility record
8. Reviewer decision and exceptions

Never say “the model is valid.” Say “passed configured checks,” “result reproduced under this environment,” “requires domain review,” or “unsupported by this version.”

## 19. Cost and hosting

The portfolio and pilot version can remain free using Python, SQLite, local files, local containers, HTML reports, and an optional local open-weight model.

A hosted product eventually incurs compute, storage, monitoring, and inference costs. The likely architecture is a lightweight SaaS control plane plus customer-hosted runners so proprietary code and heavy execution remain with the customer.

## 20. Schedule

Assuming 10–15 hours per week:

| Period | Product work | Discovery work |
|---|---|---|
| Weeks 1–2 | Version schemas and design runner | First 8 interviews |
| Weeks 3–4 | Restricted reproducible runner | Complete 15 interviews and choose ICP |
| Weeks 5–6 | Runtime instrumentation | Secure 3 pilot commitments |
| Weeks 7–8 | High-confidence checks | Collect pilot artifacts |
| Weeks 9–10 | Group-split counterfactual | Compare manual and automated review |
| Weeks 11–12 | Add/evaluate AI investigator | Reviewer-time study |
| Weeks 13–14 | Improve reporting and packaging | External pilots |
| Weeks 15–16 | GitHub check if demanded | Commercial go/no-go decision |

Advancement depends on exit criteria, not elapsed weeks.

## 21. Risks

| Risk | Mitigation |
|---|---|
| Existing products cover the need | Focus on reproduction, evidence, policies, and workflow; validate with customers |
| Coding agents absorb review | Remain an external gate with protected policies and evaluation assets |
| Arbitrary code creates security risk | Containers, narrow compatibility, limits, and security tests |
| Instrumentation changes behavior | Differential instrumented/uninstrumented testing |
| False positives destroy trust | Runtime evidence, calibrated severity, benchmark regressions |
| Domain semantics are missing | Explicit manifest, questions, abstention, policy plugins |
| Local model quality is weak | Deterministic report first; provider comparison later |
| Customer data cannot leave | Local/customer-hosted runner |
| Scope grows into MLOps | Fixed initial contract and pilot-driven expansion |
| Academic enthusiasm implies false demand | Separate usability pilots from commercial interviews |
| Regulatory claims are overextended | Never present the product as certification or automatic compliance |

## 22. Ordered implementation backlog

### 1. Versioned schemas — completed

The report contract now uses schema version `1.6.0`, immutable slotted models, explicit round-trip serialization, controlled enums, unique identifiers, and evidence-reference validation. Execution records use their own `1.6.0` contract, and runtime traces have an independently versioned `1.3.0` contract.

### 2. Runner protocol — completed

The audit flow now accepts a runner interface independent of Docker. Its request fixes the execution ID, inputs, working directory, resource limits, and network policy. The result distinguishes success, cell failure, timeout, and runner errors. A deterministic fake covers orchestration and repeated-output scenarios without starting a container.

### 3. Restricted container image — completed

The Docker backend stages only declared inputs and runs as a non-root user with networking disabled, a read-only root filesystem, dropped capabilities, no privilege escalation, and CPU, memory, process, output, and wall-time limits. It captures successful fingerprints, cell failures, timeouts, and runner failures. Automated tests cover the generated security command and input staging. Live container tests confirmed successful example execution, stable output fingerprints, exact cell-error attribution, timeout cleanup, and blocking of unstaged host files, host environment variables, writes to the input mount, and external network connections.

### 4. Normalized metric artifact — completed

The runner captures supported scikit-learn metric calls inside the notebook kernel and records the normalized name, finite value, original cell, sample count, capture method, and safe scalar parameters. A declared manifest variable is used only when the expected metric was not observed through instrumentation. If neither source produces a finite number, execution still succeeds but the metric artifact is explicitly `unsupported` and the overall audit remains `incomplete`.

### 5. Repeated execution comparison — completed

Container execution now runs twice by default. The comparison preserves ordered primary-metric values, an absolute delta with a fixed tolerance, normalized output equality, and environment equality. Environment fingerprints cover the Python runtime, operating system, architecture, runner code, and installed packages without publishing the full package inventory. Supported divergence creates an evidence-backed finding; a failed run or missing comparison signal keeps the audit `incomplete`.

### 6. Instrumentation schema — initial supported surface completed

Split, transform, fit, predict, and metric events record a stable sequence, original cell, fully qualified operation, safe scalar parameters, and input/output shape metadata. Run-scoped HMAC fingerprints preserve within-execution lineage without storing raw values or an exportable key. The pinned runner benchmark exercises all five event types. Custom and third-party operations remain explicitly outside this initial support boundary.

### 7. Entity-overlap check — initial supported implementation completed

The runner measures overlap when the configured entity column or named series is passed through supported `train_test_split` instrumentation. It returns only train/test unique counts, overlap count, and test-overlap rate. Confirmed overlap creates a blocking, high-confidence finding; missing lineage is `unsupported` and makes the audit incomplete rather than passing by inference.

### 8. Preprocessing-order check — initial supported implementation completed

Transformer-fit events are compared with earlier supported split events and run-scoped fingerprints. Fitting before a split, on the full pre-split input, or on the test output produces a blocking finding; unknown lineage is `review`, and missing instrumentation is `unsupported` rather than pass.

### 9. Binary confusion-matrix evidence — initial supported implementation completed

Supported runtime metric calls now retain aggregate true-negative, false-positive, false-negative, and true-positive counts relative to the manifest positive class. One-class evaluation slices are valid binary evidence with zero counts for the absent class; continuous-score, multiclass, and manifest-variable paths preserve an unsupported reason without exposing labels or predictions.

### 10. Group-split counterfactual

Create reversible execution lineage and show metric changes without modifying the source notebook.

### 11. Investigator benchmark before agent code

Define expected summaries and reviewer questions for at least 10 cases. The future agent must beat the deterministic baseline on usefulness without reducing factual support.

## 23. Success definitions

### Portfolio success

- restricted execution, instrumentation, deterministic checks, agent tool use, evaluation, and observability are demonstrated;
- a public benchmark and honest limitations exist;
- at least 3 real users complete an audit;
- at least 1 non-seeded issue is discovered;
- the project tells a coherent engineering story rather than collecting AI terms.

### Product success

- a team uses ValidityCI in a recurring review process;
- reviewers can inspect and challenge its evidence;
- it reduces review effort or prevents a meaningful error;
- a buyer shows willingness to pay or signs a pilot;
- use repeats across model changes or projects.

If commercial discovery fails, publish the technical system and benchmark, document what was learned, and pivot based on observed pain. Avoiding an unsupported SaaS build is a successful engineering outcome.
