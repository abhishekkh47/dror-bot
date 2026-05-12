# Phase 5 — Execution Evaluation & Reliability

Continues from `3_knowledge_modeling.md` (Phase 4: Knowledge Modeling & Retrieval Semantics).

Phase 4 delivered a fully governed operational retrieval infrastructure — metadata-driven filtering, lifecycle-aware scoring, evidence validation, confidence modeling, response governance, reasoning validation, fallback handling, and structured execution results (`ExecutionResult`). The system now produces executable AI workflow state, not just response text.

**The new bottleneck:** The evaluation system is still shallow and response-text-oriented. It measures phrase presence and basic contradictions in the final response, but the architecture is now much richer than that. Evals must evolve from **response evaluation** to **execution evaluation**.

**Key principle:** Production AI evals should measure **system behavior**, not merely final text output. A response may look correct while retrieval confidence collapsed, reasoning validator triggered, fallback mode activated, or evidence quality was weak. That is hidden instability — production systems must detect it.

---

## Step 4.19: Execution-level evaluation framework

**Category:** Operational AI Reliability Measurement

**What:** Extended the eval system from response-text-only evaluation to execution-level evaluation that measures internal pipeline behavior. The eval harness now consumes the full `ExecutionResult` and tracks retrieval confidence, response mode, reasoning issues, and quality scores alongside the existing phrase-based checks.

**The problem — evaluating responses while ignoring execution state:**

The eval system asked "did the answer look correct?" but enterprise systems need "how did the system behave internally?" A response may pass all phrase checks while:
- Retrieval confidence was 0.18 (dangerously low)
- Reasoning validator triggered 3 contradictions
- Fallback mode activated (system refused to reason)
- Quality score dropped to 25/100

Without execution metrics, these silent regressions are invisible. Future architecture changes that increase fallback frequency, reduce retrieval confidence, or trigger more reasoning violations would go undetected if the final response text still "looks okay."

**What was built:**

**`app/tests/evals/execution_metrics.py`** — `build_execution_metrics(result)`:

Extracts structured execution telemetry from `ExecutionResult`:
- `quality_score` — 0–100 operational quality rating
- `retrieval_confidence` — evidence strength estimation
- `response_mode` — normal / cautious / clarification / fallback
- `reasoning_issue_count` — number of consistency violations detected
- `has_reasoning_issues` — boolean flag for quick filtering

Intentionally simple — telemetry infrastructure bootstrap, not a full analytics platform.

**`app/tests/evals/evaluator.py`** — Updated `run_all_evals()`:
- Now consumes `ExecutionResult` from `ask_with_context()` instead of raw string
- Calls `build_execution_metrics(result)` for each test case
- Displays execution metrics alongside response and pass/fail results

**Eval output now shows:**

```
RESPONSE:
<response text>

EXECUTION METRICS:
- quality_score: 75
- retrieval_confidence: 0.52
- response_mode: cautious
- reasoning_issue_count: 1
- has_reasoning_issues: True

PASSED: True
```

**The architectural transition:**

| Before | After |
|--------|-------|
| Evals measure response text appearance | Evals measure operational execution behavior |
| Silent regressions invisible | Confidence/mode/reasoning trends measurable |
| Pass/fail = phrase presence only | Pass/fail + execution quality metrics |
| Dead telemetry in pipeline | Telemetry consumed by eval infrastructure |

**Why this matters:** Production AI systems eventually become **telemetry systems**, not merely response systems. This step connects the execution telemetry (built across Steps 4.10–4.18) to the evaluation infrastructure (built in Step 3.7), closing the loop between operational governance and reliability measurement.

**What this step did NOT change:**
- No retrieval changes, no prompt changes, no model changes
- Metrics are displayed but not yet used for automated regression detection (trend analysis, threshold alerts)
- Eval still uses phrase-based pass/fail — execution metrics are additive observability, not replacement

**Next step:** Step 4.20 — Retrieval Regression Benchmarking. The system still lacks retrieval recall benchmarks, retrieval precision tracking, chunk selection quality measurement, lifecycle-grounding scoring, and retrieval drift detection. That becomes the next major reliability frontier.

---

## Step 4.20: Retrieval regression benchmarking

**Category:** Retrieval Reliability Infrastructure

**What:** Added retrieval coverage evaluation that measures the quality of retrieved chunks directly — lifecycle diversity, operational evidence presence, troubleshooting coverage — instead of only measuring final response quality. Also expanded `ExecutionResult` to expose `selected_chunks`, making internal retrieval state available to the eval system.

**The problem — measuring generation while ignoring retrieval:**

The eval system measured execution telemetry (confidence, mode, reasoning issues) but still could not answer: did retrieval actually find the right evidence? Generation quality is downstream — the real root cause of regressions often lives in retrieval degradation. Modifying metadata weighting, lifecycle selectors, chunk ranking, or suppression rules could silently cause cancellation evidence to disappear, troubleshooting chunks to dominate, or lifecycle chronology to weaken. The response may still look acceptable while retrieval quality has already degraded badly.

**Key principle:** Enterprise RAG systems should measure **retrieval correctness directly**, not only final response quality.

**What was built:**

1. **`app/tests/evals/retrieval_metrics.py`** — `evaluate_retrieval_quality(selected_chunks)`:

   Evaluates operational retrieval coverage:
   - `chunk_count` — number of selected chunks
   - `lifecycle_coverage` — True if >= 2 distinct lifecycle stages present (chronology evidence diversity)
   - `operational_coverage` — True if `operational_behavior` knowledge type present (reasoning evidence)
   - `troubleshooting_coverage` — True if `troubleshooting` knowledge type present (debugging evidence)

   This is **operational retrieval coverage evaluation**, not semantic retrieval evaluation. It validates lifecycle grounding, metadata diversity, and evidence composition — the correct starting point before semantic ranking precision or retrieval recall scoring.

2. **`app/core/types.py`** — `ExecutionResult` expanded with `selected_chunks: list`:

   Retrieval-stage state was previously trapped inside `retrieval_context` (only accessible within the pipeline). Now `selected_chunks` flows through `ExecutionResult` to the eval system, making internal retrieval state inspectable from outside the pipeline.

3. **`app/core/llm/rag_pipeline.py`** — Extracts `selected_chunks` from `retrieval_context` and includes it in `ExecutionResult`:

   ```python
   selected_chunks = retrieval_context["selected_chunks"]
   ```

   This was necessary because `selected_chunks` existed inside `build_retrieval_context()` but `ask_with_context()` never exposed it after the retrieval orchestration extraction in Step 4.3.

4. **`app/tests/evals/evaluator.py`** — `run_all_evals()` now calls `evaluate_retrieval_quality(result.selected_chunks)` and displays retrieval metrics alongside execution metrics.

**Eval output now shows:**

```
RESPONSE:
<response text>

EXECUTION METRICS:
- quality_score: 75
- retrieval_confidence: 0.52
- response_mode: cautious
- reasoning_issue_count: 1
- has_reasoning_issues: True

RETRIEVAL METRICS:
- chunk_count: 4
- lifecycle_coverage: True
- operational_coverage: True
- troubleshooting_coverage: False
```

**The architectural transition:**

| Before | After |
|--------|-------|
| Retrieval quality = implicit assumption | Retrieval quality = measurable infrastructure state |
| Retrieval regressions invisible until generation fails | Retrieval coverage tracked per evaluation run |
| Only response text and execution telemetry measured | Retrieval composition directly inspectable |

**Why this matters:** When you eventually change metadata rules, chunk ranking, retrieval scoring, suppression logic, or lifecycle selectors, retrieval benchmarks will immediately show whether lifecycle coverage dropped, operational evidence disappeared, or troubleshooting chunks vanished — before you even look at the generated response.

**What this step did NOT change:**
- No retrieval logic changes, no prompt changes
- Retrieval metrics are coverage-based, not precision/recall (semantic retrieval evaluation comes later)
- Metrics are displayed but not yet used for automated threshold-based regression alerts

**Next step:** Step 4.21 — Lifecycle Drift Detection. The system still does not detect lifecycle inconsistencies across retrieval, chronology weakening, retrieval-stage conflicts, or operational evidence drift. That becomes the next major reliability and reasoning frontier.

---

## Step 4.21: Lifecycle drift detection

**Category:** Operational Chronology Integrity

**What:** Added retrieval-level lifecycle integrity validation that detects contradictory evidence across retrieved chunks before generation. The system now validates whether retrieved evidence forms a coherent chronology and flags operational invariant violations. This is **retrieval integrity validation** — a fundamentally different layer from response validation (Step 4.14) or prompt governance (Step 4.11).

**The problem — inconsistent retrieval evidence:**

Steps 4.14–4.15 validate generated reasoning and constrain response behavior, but the underlying retrieval evidence itself may already be inconsistent. Retrieved chunks may simultaneously imply `processing_started = True` and `intent creation failed`, or `cancellation before processing`, or `completion after rollback`. Even if generation constraints suppress some contradictions in the final response, the grounding is corrupted. Generated contradictions often originate from **inconsistent retrieval evidence**, not bad prompting.

**Key principle:** Validating generated reasoning is necessary but insufficient. Enterprise systems must also validate **retrieval evidence consistency** — the integrity of the grounding layer itself.

**What was built:**

**`app/core/rag/lifecycle_drift.py`** — `detect_lifecycle_drift(lifecycle_facts, selected_chunks)`:

Two categories of drift detection:

1. **Lifecycle fact invariant violations:**
   - `processing_started` without `intent_created` → "Processing started without intent creation"
   - `transaction_cancelled` without `processing_started` → "Cancellation occurred without processing evidence"

2. **Contradictory lifecycle stage co-occurrence in retrieved chunks:**
   - Defined contradictory pairs (e.g., `intent_creation_failed` + `processing` cannot coexist)
   - Scans metadata lifecycle stages across all selected chunks

Returns a list of drift issues.

**Pipeline integration:**
- `rag_pipeline.py` — calls `detect_lifecycle_drift()` before generation reasoning validation, merges drift issues into `reasoning_issues` (lifecycle drift IS reasoning instability)
- `ExecutionResult` — expanded with `lifecycle_drift_issues: list[str]` to expose drift separately from response reasoning issues

**Validation layers after this step (each at a different architectural level):**

| Layer | What it validates | When it runs |
|-------|-------------------|--------------|
| Retrieval validation (4.8) | Evidence sufficiency | After chunk selection |
| Lifecycle drift detection (4.21) | Retrieval evidence consistency | Before generation |
| Reasoning validation (4.14) | Generated response consistency | After generation |
| Sanitization | Wording normalization | After validation |

**What this changes architecturally:**

| Before | After |
|--------|-------|
| Retrieval evidence assumed coherent | Retrieval evidence explicitly validated for chronology integrity |
| Contradictions only caught post-generation | Contradictions detected at retrieval level before generation |
| Prompt tuning blamed for contradictions | Retrieval evidence corruption exposed as root cause |

**Expected effects:**
- Contradictory retrieval evidence becomes detectable before it reaches the model
- Debugging shifts from "why did the model say X?" to "why did retrieval contain conflicting evidence?"
- Retrieval tuning becomes safer — lifecycle integrity is now measured

**Important — do NOT massively expand drift rules yet:** Focus on high-signal operational invariants and chronology integrity. This is drift detection infrastructure, not a giant rule engine.

**What this step did NOT change:**
- No retrieval logic changes — drift is detected, not corrected
- Drift issues are logged and tracked in `ExecutionResult`, not yet used to trigger retrieval retries or correction

**Next step:** Step 4.22 — Adaptive Retrieval Correction. The system can now detect weak retrieval, lifecycle drift, low confidence, and evidence insufficiency — but it still cannot adapt retrieval behavior dynamically. Retrieval retries, dynamic filtering relaxation, retrieval expansion, evidence recovery, and adaptive chunk selection become the next frontier: **self-correcting retrieval infrastructure**.

---

## Step 4.22: Adaptive retrieval correction (detection phase)

**Category:** Self-Correcting Retrieval Infrastructure

**What:** Introduced adaptive retrieval recovery decision infrastructure — the system now determines whether retrieval should attempt recovery based on confidence and lifecycle drift, and builds a recovery strategy. This step is the **detection and decision phase** — recovery execution comes in the next step. Correct rollout: detect → decide → THEN execute.

**The problem — detection without adaptation:**

The system can detect low confidence, weak coverage, lifecycle drift, and reasoning instability. But retrieval behavior remains static — same strategy, same filters, same selection logic, same retrieval depth regardless of detected quality. Weak retrieval produces unnecessary fallback responses, missing evidence, incomplete chronology, and weak operational reasoning. Detection without adaptation is incomplete.

**Key principle:** If the system can detect retrieval weakness, it should eventually attempt recovery.

**What was built:**

**`app/core/rag/retrieval_recovery.py`** — Two functions:

1. `should_retry_retrieval(retrieval_confidence, lifecycle_drift_issues)`:
   - Returns `True` if `retrieval_confidence < 0.35` (evidence too weak)
   - Returns `True` if `lifecycle_drift_issues` exist (evidence internally contradictory)
   - Returns `False` otherwise
   - Deterministic and bounded — NOT recursive agents, NOT infinite retry loops, NOT LLM-driven retrieval planning

2. `build_recovery_strategy()`:
   - Returns recovery parameters: `increase_top_k`, `relax_similarity_threshold`, `allow_adjacent_lifecycle_stages`
   - Strategy is built but NOT YET EXECUTED — infrastructure shape first

**Pipeline integration:**
- `rag_pipeline.py` — after lifecycle drift detection and reasoning issue merging, calls `should_retry_retrieval()` and conditionally builds `recovery_strategy`
- `ExecutionResult` — expanded with `retrieval_recovery_eligible: bool` to expose whether recovery was warranted

**What this changes architecturally:**

| Before | After |
|--------|-------|
| Retrieval failures are terminal states | Recoverable retrieval failures are identified |
| Static retrieval — same strategy always | Adaptive retrieval state exposed |
| Detection without action | Detection → decision → (future) execution |

**Why recovery is not executed yet:**

Executing retries without proper infrastructure creates runaway retrieval, noisy evidence expansion, and retrieval instability. The correct sequencing:

| Phase | Purpose | Status |
|-------|---------|--------|
| Detect | Identify weak retrieval | Done (Steps 4.10, 4.20, 4.21) |
| Decide | Determine if recovery is warranted | Done (this step) |
| Execute | Perform bounded retries | Next step (4.23) |

Observability, retry policies, retry metrics, retry boundaries, and retry safety must exist before execution.

**What this step did NOT change:**
- No retrieval logic changes — recovery is decided but not executed
- No retry loops, no re-retrieval, no filtering relaxation yet
- Recovery strategy is a static policy — not yet dynamically tuned per query

**Next step:** Step 4.23 — Controlled Retrieval Retry Execution. The system actually performs bounded retries: adaptive top-k expansion, similarity threshold relaxation, adjacent lifecycle recovery, evidence augmentation. The first true adaptive retrieval execution layer.

---

## Step 4.23–4.24: Controlled retrieval retry execution + retry effectiveness telemetry

**Category:** Self-Correcting Retrieval Infrastructure + Adaptive Retrieval Observability

Two tightly coupled steps implemented together: the system now executes bounded retrieval retries when recovery is warranted AND exposes full retry telemetry so retry effectiveness is measurable. Adaptive behavior without observability creates invisible instability — so execution and telemetry were built in the same pass.

### Step 4.23: Controlled retrieval retry execution

**What:** The retrieval pipeline now performs a single bounded retry when `retrieval_recovery_eligible` is true. The retry uses a modified retrieval strategy (increased `top_k`, relaxed similarity threshold, adjacent lifecycle stages allowed), re-processes the new chunks through the full pipeline (`process_retrieved_chunks`), and keeps the better result based on confidence comparison.

**Implementation in `retrieval_pipeline.py`:**

The `build_retrieval_context()` function was refactored:
- Core chunk processing (filtering → noise suppression → lifecycle extraction → selection → LLM refinement → validation → confidence → distillation → evidence → timeline) was extracted into `process_retrieved_chunks()` — reusable for both initial retrieval and retry
- After initial retrieval, if `retrieval_recovery_eligible` is true:
  1. Builds recovery strategy via `build_recovery_strategy()`
  2. Applies strategy to retrieval options (`apply_recovery_strategy()` — increases `top_k`, relaxes thresholds)
  3. Executes retry: `store.search()` with modified options → `process_retrieved_chunks()` on retry results
  4. Compares retry confidence against initial confidence
  5. Keeps whichever result has higher confidence — retry does NOT blindly replace

**Key design decisions:**
- **Single retry only** — no recursive retries, no infinite loops, no autonomous retry planning
- **Confidence-gated replacement** — retry result only replaces initial if `retry_confidence > retrieval_confidence`
- **Full pipeline re-execution** — retry chunks go through the same filtering, selection, validation, and distillation as initial retrieval, not a shortcut

### Step 4.24: Retry effectiveness telemetry

**What:** Made adaptive retrieval fully observable by exposing retry state as first-class execution telemetry, not hidden behavior.

**`app/core/types.py`** — `ExecutionResult` expanded:
- `retry_attempted: bool` — whether a retry actually executed
- `initial_retrieval_confidence: float` — confidence before retry
- `final_retrieval_confidence: float` — confidence after retry (or same as initial if no retry)
- `retry_confidence_delta: float` — confidence improvement (or degradation)

**`retrieval_pipeline.py`** — Propagates telemetry through `retrieval_context`:
```python
retrieval_context["retry_attempted"] = retry_attempted
retrieval_context["initial_retrieval_confidence"] = initial_retrieval_confidence
retrieval_context["final_retrieval_confidence"] = retrieval_context.get("retrieval_confidence", 0.0)
retrieval_context["retry_confidence_delta"] = retry_confidence_delta
```

**`rag_pipeline.py`** — Extracts retry telemetry from `retrieval_context` and includes it in `ExecutionResult`.

**What retry telemetry enables:**

| Question | Now measurable |
|----------|---------------|
| Are retries helping? | `retry_confidence_delta > 0` |
| Are retries increasing hallucinations? | Compare quality scores with/without retry |
| Which queries trigger retries most? | Filter by `retry_attempted = True` |
| Is retry quality improving over time? | Track delta trends |
| Is retry logic worth keeping? | Aggregate success rate |

**The architectural transition:**

| Before | After |
|--------|-------|
| Retrieval failures are terminal | Retrieval failures trigger bounded recovery |
| Adaptive retrieval is hidden behavior | Adaptive retrieval is observable orchestration state |
| Recovery effectiveness unmeasurable | Confidence delta exposes retry value |
| Static retrieval — same strategy always | Dynamic retrieval with telemetry-visible adaptation |

**What this step did NOT change:**
- Single retry only — no multiple retries, no recursive retries, no autonomous retry planning
- Retry is confidence-gated, not always-replace
- Recovery strategy is static (`build_recovery_strategy()`) — not yet dynamically tuned per query or failure type
- Retry metrics are exposed in `ExecutionResult` but not yet consumed by the eval system for automated benchmarking

**Important — correct rollout sequencing for adaptive systems:**

| Phase | Purpose | Status |
|-------|---------|--------|
| Detect | Identify weak retrieval | Done (Steps 4.10, 4.20, 4.21) |
| Decide | Determine if recovery is warranted | Done (Step 4.22) |
| Execute | Perform bounded retry | Done (Step 4.23) |
| Observe | Measure retry effectiveness | Done (Step 4.24) |
| Tune | Optimize retry policies based on data | Next frontier |

Enterprise AI principle: adaptive systems without telemetry become invisible instability systems.

---

## Step 4.25: Retrieval quality comparison engine

**Category:** Adaptive Retrieval Evaluation

**What:** Replaced the primitive single-metric retry evaluation (`retry_confidence > initial_confidence`) with a multi-factor retrieval quality comparison engine. Retries are now selected based on holistic retrieval quality — confidence, chunk coverage, and lifecycle timeline completeness — not just a single confidence score.

**The problem — confidence is a weak retrieval quality signal:**

Higher confidence does NOT necessarily mean better evidence, cleaner chronology, lower hallucination risk, or safer operational reasoning. A retry may retrieve more chunks, increase metadata diversity, and increase the confidence score — while simultaneously introducing noisy troubleshooting chunks, contradictory lifecycle evidence, infra leakage, and hallucination risk. The previous logic (`if retry_confidence > retrieval_confidence: keep retry`) could not detect this — creating noisy retry upgrades, hidden retrieval degradation, and unstable chronology grounding.

**Key principle:** Adaptive retrieval should optimize **retrieval quality**, not merely confidence score.

**What was built:**

**`app/core/rag/retrieval_comparator.py`** — `compare_retrieval_quality(initial_context, retry_context)`:

Multi-factor scoring comparison:

| Signal | Weight | Why |
|--------|--------|-----|
| Retrieval confidence | × 100 | Evidence strength estimation |
| Chunk count (capped at 5) | × 5 per chunk | Evidence volume (bounded to prevent noise reward) |
| Lifecycle timeline length | × 5 per event | Chronology completeness |

Computes separate scores for initial and retry, returns `True` if retry score exceeds initial.

**Pipeline integration:** In `retrieval_pipeline.py`, the old confidence-only comparison was replaced:

```python
# Before: if retry_confidence > retrieval_confidence
# After:
retry_is_better = compare_retrieval_quality(
    initial_context=retrieval_context,
    retry_context=retry_context,
)
if retry_is_better:
    retrieval_context = retry_context
```

**What this changes:**

| Before | After |
|--------|-------|
| Retry evaluated by confidence only | Retry evaluated by confidence + coverage + timeline |
| Noisy retries accepted if confidence higher | Noisy retries rejected if evidence quality lower |
| Adaptive retrieval optimizes one metric | Adaptive retrieval optimizes holistic quality |

**Design decisions:**
- Chunk count capped at 5 to prevent rewarding evidence volume over evidence quality
- Scoring is intentionally simple and deterministic — retrieval quality comparison infrastructure, not mathematically optimal retrieval scoring
- Explainable, bounded, observable — not an opaque scoring system

**What this step did NOT change:**
- No retrieval logic changes, no prompt changes
- Scoring weights are not tuned — infrastructure shape first
- Does not yet incorporate reasoning drift, knowledge type diversity, or transport suppression quality into comparison

**Next step:** Step 4.26 — Retrieval Stability Analysis. The system still does not measure retrieval consistency across retries, retrieval volatility, unstable chunk selection, metadata instability, or lifecycle fluctuation. That becomes the next major reliability frontier: retrieval stability engineering.

---

## Step 4.26: Retrieval stability analysis

**Category:** Retrieval Reliability Engineering

**What:** Introduced retrieval stability scoring that measures consistency between initial retrieval and retry retrieval. The system now evaluates adaptive retrieval on both **quality** (Step 4.25) and **stability** — detecting when retries produce volatile, inconsistent evidence even if quality scores improve.

**The problem — quality without stability:**

The quality comparison engine (Step 4.25) determines which retrieval is better. But it does not measure whether retrieval behavior is consistent. The same query may produce different lifecycle stages, different chunk compositions, different confidence levels, and different operational conclusions across retries — even when the query barely changed. That is **retrieval volatility**, and it leads to unstable reasoning, inconsistent support answers, trust degradation, and debugging nightmares.

**Key principle:** Enterprise retrieval systems need BOTH retrieval quality AND retrieval stability. A highly variable system becomes operationally unpredictable even when individual retrievals are acceptable.

**What was built:**

**`app/core/rag/retrieval_stability.py`** — `analyze_retrieval_stability(initial_context, retry_context)`:

Starts at 100 (perfectly stable), penalizes volatility across three dimensions:

| Signal | Max penalty | What it measures |
|--------|-------------|-----------------|
| Chunk overlap ratio | -40 | How many of the same chunks survived across attempts (low overlap = high volatility) |
| Confidence fluctuation | -30 | Absolute confidence delta between attempts (large swings = instability) |
| Lifecycle timeline overlap | -30 | Whether the same lifecycle events appear in both timelines (divergent chronology = dangerous) |

Score range: 0 (completely unstable) to 100 (perfectly stable).

**Pipeline integration:**
- `retrieval_pipeline.py` — computes stability score inside the retry block (comparing initial and retry contexts), defaults to 100 when no retry attempted, propagates through `retrieval_context`
- `rag_pipeline.py` — extracts `retrieval_stability_score` from retrieval context
- `ExecutionResult` — expanded with `retrieval_stability_score: int = 100`

**What this changes:**

| Before | After |
|--------|-------|
| Adaptive retrieval evaluated by quality only | Evaluated by quality + stability |
| Volatile retries invisible | Volatility measured and exposed |
| Chunk composition changes untracked | Chunk overlap ratio quantified |
| Confidence swings undetected | Confidence fluctuation penalized |
| Timeline divergence unmeasured | Lifecycle timeline overlap tracked |

**Important — stability != rigidity:**

Some variability is healthy (retries finding better evidence means chunk composition changes). The goal is measuring **volatility risk**, not enforcing rigid determinism. Over-penalizing variation would freeze retrieval diversity.

**What this step did NOT change:**
- No retrieval logic changes — stability is measured, not enforced
- Stability score is exposed in `ExecutionResult` but not yet used to gate retry acceptance (future evolution)
- Scoring weights are approximate — infrastructure shape first, tuning via eval data later

**Next step:** Step 4.27 — Lifecycle Evidence Coherence Scoring. The system still does not explicitly measure chronology coherence, causal consistency, operational narrative integrity, or lifecycle evidence alignment. That becomes the next major reasoning-quality frontier: evidence coherence engineering.

---

## Step 4.27: Lifecycle evidence coherence scoring

**Category:** Operational Narrative Integrity

**What:** Introduced lifecycle coherence scoring that measures whether retrieved evidence forms a valid operational narrative — not just whether individual chunks are relevant, high-confidence, and stable. The system now evaluates chronology continuity by matching the lifecycle timeline against known valid lifecycle flows.

**The problem — relevance without coherence:**

Retrieved evidence may individually be relevant, high confidence, and stable, yet collectively form a fragmented or incoherent chronology. Example: `processing_started`, `cancellation`, `refund_pending`, `authentication_required` may all be semantically relevant, yet the operational story becomes incoherent — there is no valid lifecycle flow that connects them. That creates confusing explanations, weak reasoning, and contradictory support guidance.

**Key principle:** Operational correctness requires **evidence coherence**, not merely retrieval relevance.

**What was built:**

**`app/core/rag/lifecycle_coherence.py`** — `score_lifecycle_coherence(lifecycle_timeline)`:

Defines canonical valid lifecycle flows and scores timeline adherence:

```python
VALID_LIFECYCLE_FLOWS = [
    ["intent_created", "processing_started", "processing_failed", "transaction_cancelled"],
    ["intent_created", "processing_started", "completed"],
]
```

Scoring:
- Normalizes timeline events (lowercase, strip periods)
- For each valid flow, counts how many stages appear in the timeline
- Score = `(matches / flow_length) * 100`, keeps the best match across all valid flows
- Range: 0 (no coherence — timeline doesn't match any valid flow) to 100 (full chronology match)

**Pipeline integration:**
- `retrieval_pipeline.py` — computes coherence score inside `process_retrieved_chunks()` after timeline construction, includes in return dict
- `rag_pipeline.py` — extracts `lifecycle_coherence_score` from retrieval context
- `ExecutionResult` — expanded with `lifecycle_coherence_score: int = 0`

**What this adds to the measurement stack:**

| Metric | What it measures | Step |
|--------|-----------------|------|
| Retrieval confidence | Evidence strength | 4.10 |
| Retrieval coverage | Lifecycle/operational diversity | 4.20 |
| Lifecycle drift | Evidence contradictions | 4.21 |
| Retrieval stability | Consistency across retries | 4.26 |
| **Lifecycle coherence** | **Operational narrative integrity** | **4.27** |

Previously the system could tell you: "retrieval is confident, stable, and non-contradictory." Now it can also tell you: "but the evidence doesn't form a coherent operational story" — a completely different failure mode.

**What this step did NOT change:**
- No retrieval logic changes — coherence is measured, not enforced
- Valid lifecycle flows are hardcoded — will need expansion as more workflows are added
- Coherence score is not yet used to gate generation or trigger retries

**Next step:** Step 4.28 — Operational Evidence Conflict Detection. The system still does not explicitly detect conflicting operational claims, mutually incompatible evidence, contradictory failure causes, or impossible operational combinations. That becomes the next major reasoning integrity frontier: evidence conflict governance.

---

## Step 4.28: Operational evidence conflict detection

**Category:** Operational Reasoning Integrity

**What:** Added explicit detection of operationally incompatible evidence — mutually exclusive lifecycle states, contradictory outcomes, and impossible transaction state combinations. This is a different layer from chronology drift (Step 4.21, retrieval-level) and reasoning validation (Step 4.14, response-level). Evidence conflicts are **operational compatibility violations** — individually valid evidence that is collectively impossible.

**The problem — compatible evidence != compatible operations:**

Retrieved evidence may be individually valid, chronologically coherent, high-confidence, and stable — yet still form impossible operational states. Example: evidence simultaneously suggesting `payment completed`, `transaction cancelled`, `authentication required`, and `processing never started` are all individually plausible chunks, but together they describe an impossible transaction. This creates misleading support guidance, contradictory root-cause explanations, and unstable troubleshooting behavior.

**Key principle:** Operational reasoning quality depends on **evidence compatibility**, not merely evidence coherence. Coherence checks chronology ordering. Compatibility checks operational possibility.

**What was built:**

**`app/core/rag/evidence_conflicts.py`** — `detect_operational_conflicts(lifecycle_facts, operational_evidence)`:

Conflict detection from two sources:

1. **Lifecycle facts** → detected states (`processing_started`, `transaction_cancelled`, `final_state`)
2. **Operational evidence text** → inferred states (e.g., "authentication" keyword → `authentication_required`)

Checked against conflict rules:

| State A | State B | Why impossible |
|---------|---------|---------------|
| `completed` | `transaction_cancelled` | Completed transactions cannot be cancelled |
| `processing_started` | `processing_never_started` | Mutually exclusive states |
| `authentication_required` | `completed` | Cannot complete if auth is still required |

Returns list of conflict descriptions.

**Pipeline integration:**
- `retrieval_pipeline.py` — detects conflicts inside `process_retrieved_chunks()` after building operational evidence, includes in return dict
- `rag_pipeline.py` — extracts `operational_conflicts`, merges them into `reasoning_issues` (operational conflicts ARE reasoning integrity violations)
- `ExecutionResult` — expanded with `operational_conflicts: list[str] = []`

**Important distinction — three validation layers at different levels:**

| Layer | What it validates | Architectural level |
|-------|-------------------|-------------------|
| Lifecycle drift (4.21) | Retrieval evidence chronology consistency | Retrieval integrity |
| Evidence conflicts (4.28) | Operational state compatibility | Operational integrity |
| Reasoning validation (4.14) | Generated response consistency | Response integrity |

Drift = "does evidence form valid chronology?" Conflicts = "are operational claims mutually possible?" Reasoning = "did the model reason correctly from evidence?"

**What this step did NOT change:**
- No retrieval logic changes — conflicts are detected, not corrected
- Conflict rules are minimal (3 rules) — focus on high-signal contradictions and obvious operational impossibilities
- Conflicts feed into reasoning issues and `ExecutionResult` but don't yet trigger response downgrading or retries

**Next step:** Step 4.29 — Adaptive Response Downgrading. The system still does not automatically reduce answer certainty, troubleshooting specificity, or causal confidence when evidence conflicts exist, coherence is weak, or retrieval stability is low. That becomes the next major trustworthiness frontier: response reliability adaptation.

---

## Step 4.29: Adaptive response downgrading

**Category:** Reliability-Aware Response Governance

**What:** Introduced a composite response reliability score that aggregates retrieval confidence, lifecycle coherence, retrieval stability, and operational conflicts into a single trustworthiness signal. Response mode determination now uses this reliability score as the primary gate — the system gracefully degrades response behavior when overall reasoning integrity is weak, not just when retrieval confidence is low.

**The problem — confidence without integrity:**

High retrieval confidence can coexist with operational conflicts, weak coherence, and unstable retrieval. Example: `confidence = 0.82` but `lifecycle_coherence = 35`, `retrieval_stability = 42`, and operational conflicts detected. That is an unreliable operational state, yet the previous confidence-only response governance would still allow detailed troubleshooting, causal claims, and failure attribution. Dangerous in enterprise support systems.

**Key principle:** Enterprise AI systems should degrade gracefully under uncertainty — not merely soften wording slightly. Response certainty should depend on **total reasoning integrity**, not merely retrieval confidence.

**What was built:**

1. **`app/core/rag/response_reliability.py`** — `compute_response_reliability(retrieval_confidence, lifecycle_coherence_score, retrieval_stability_score, operational_conflicts)`:

   Composite reliability scoring (starts at 100, penalizes each weakness):

   | Signal | Max penalty | Weight rationale |
   |--------|-------------|-----------------|
   | Low retrieval confidence | -40 | Evidence strength is the strongest signal |
   | Weak lifecycle coherence | -25 | Incoherent narrative undermines reasoning |
   | Low retrieval stability | -20 | Volatile retrieval undermines consistency |
   | Operational conflicts | -15 per conflict | Each conflict is a reasoning integrity violation |

   Score range: 0 (completely unreliable) to 100 (fully reliable).

2. **`app/core/rag/fallback_policy.py`** — `determine_response_mode()` upgraded with reliability governance:

   ```python
   # Reliability gates take priority
   if response_reliability_score < 40: return "fallback"
   if response_reliability_score < 60: return "clarification"
   # Then existing confidence-based logic
   if retrieval_confidence >= 0.75: return "normal"
   if retrieval_confidence >= 0.45: return "cautious"
   if retrieval_confidence >= 0.25: return "clarification"
   return "fallback"
   ```

   Reliability gates run BEFORE confidence checks — a high-confidence but low-integrity state still triggers fallback/clarification.

**Pipeline integration:**
- `rag_pipeline.py` — computes `response_reliability_score` after extracting all integrity signals, passes to `determine_response_mode()`
- `ExecutionResult` — expanded with `response_reliability_score: int = 100`

**What this changes — response behavior now depends on total reasoning integrity:**

| Scenario | Before | After |
|----------|--------|-------|
| High confidence, low coherence | Normal response | Clarification/fallback |
| High confidence, conflicts detected | Normal response | Downgraded by conflict penalty |
| High confidence, unstable retrieval | Normal response | Downgraded by stability penalty |
| Low everything | Fallback (confidence-only) | Fallback (reliability-driven) |

**Important — trust calibration, not maximal caution:** Do NOT over-penalize uncertainty, force fallback too aggressively, or collapse useful responses unnecessarily. The goal is optimizing trust calibration — making response certainty proportional to reasoning integrity.

**What this step did NOT change:**
- No retrieval logic changes, no prompt changes
- Reliability weights are approximate — tuning comes from eval data
- Response downgrading is mode-based (normal/cautious/clarification/fallback) — not yet fine-grained within modes

**Next step:** Step 4.30 — Retrieval Evidence Attribution & Source Traceability. Responses still do not explicitly expose which evidence supported which claim, which lifecycle facts were grounded, which operational conclusions were inferred, and which retrieval evidence justified the response. That becomes the next major enterprise trustworthiness frontier: explainable operational reasoning.

---

## Step 4.30: Retrieval evidence attribution & source traceability

**Category:** Explainable Operational Reasoning

**What:** Introduced evidence attribution infrastructure that tracks which chunks supported reasoning, which lifecycle facts were grounded from evidence, and which chunk IDs influenced conclusions. Responses are no longer operationally opaque — the system can now explain what evidence justified its answer.

**The problem — opaque operational reasoning:**

The system produces "The payment processing failed during auto-completion" but neither users, support engineers, nor debugging systems can see: what evidence supported that, which lifecycle facts were grounded, whether the answer was inferred or directly supported, or which chunks influenced the conclusion. This creates low auditability, weak trust, difficult debugging, and poor enterprise explainability.

**Key principle:** Enterprise AI systems require **evidence traceability**, not merely good answers. Trustworthy AI must answer: "Why did the model say this?" and "Which evidence supported this conclusion?"

**What was built:**

**`app/core/rag/evidence_attribution.py`** — `build_evidence_attribution(selected_chunks, lifecycle_facts)`:

Builds an attribution record with three dimensions:

| Field | What it tracks |
|-------|---------------|
| `supporting_topics` | Unique metadata topics from selected chunks |
| `grounded_lifecycle_facts` | Which lifecycle facts (`intent_created`, `processing_started`, `processing_failed`, `transaction_cancelled`) were confirmed from evidence |
| `evidence_chunk_ids` | IDs of all chunks that participated in reasoning |

**Example attribution output:**
```json
{
  "supporting_topics": ["auto_completion", "cancellation"],
  "grounded_lifecycle_facts": ["intent_created", "processing_started", "processing_failed", "transaction_cancelled"],
  "evidence_chunk_ids": ["chunk-001", "chunk-007", "chunk-012"]
}
```

**Pipeline integration:**
- `retrieval_pipeline.py` — builds attribution inside `process_retrieved_chunks()` after operational evidence and conflict detection, includes in return dict
- `rag_pipeline.py` — extracts `evidence_attribution` from retrieval context
- `ExecutionResult` — expanded with `evidence_attribution: dict = {}`
- `run_eval.py` — optionally displays attribution for debugging and retrieval audits

**What this enables:**

| Use case | How attribution helps |
|----------|----------------------|
| Hallucination debugging | Check if conclusion chunk IDs actually contain supporting evidence |
| Retrieval audits | Verify which topics contributed to the answer |
| Lifecycle grounding verification | Confirm which facts were evidence-based vs inferred |
| Support engineer trust | Show what the system relied on |
| Regression analysis | Track whether attribution patterns change after architecture changes |

**Important design decision — operationally practical, not research-grade:**

This is NOT token-level attribution, attention visualization, SHAP-like reasoning maps, or neural explainability. It is **operational evidence provenance** — which chunks, which topics, which lifecycle facts. Practical for debugging and auditing, not for research papers.

**Important — internal telemetry, not user-facing:** Attribution is currently internal operational telemetry. Raw chunk IDs should NOT be exposed to end users yet. User-facing explainability UI is a future layer.

**What this step did NOT change:**
- No retrieval logic changes, no prompt changes
- Attribution does not yet distinguish between directly grounded facts and inferred conclusions (that is Step 4.31)
- Attribution is passive — recorded but not used to influence generation behavior

**The full `ExecutionResult` contract after Phase 4:**

| Field | Category | Step |
|-------|----------|------|
| `response` | Output | — |
| `retrieval_confidence` | Evidence strength | 4.10 |
| `response_mode` | Behavior | 4.16 |
| `reasoning_issues` | Reasoning integrity | 4.14 |
| `quality_score` | Quality | 4.17 |
| `selected_chunks` | Retrieval state | 4.20 |
| `lifecycle_drift_issues` | Chronology integrity | 4.21 |
| `retrieval_recovery_eligible` | Adaptive retrieval | 4.22 |
| `retry_attempted` | Retry telemetry | 4.24 |
| `initial_retrieval_confidence` | Retry telemetry | 4.24 |
| `final_retrieval_confidence` | Retry telemetry | 4.24 |
| `retry_confidence_delta` | Retry telemetry | 4.24 |
| `retrieval_stability_score` | Stability | 4.26 |
| `lifecycle_coherence_score` | Narrative integrity | 4.27 |
| `operational_conflicts` | Operational compatibility | 4.28 |
| `response_reliability_score` | Composite reliability | 4.29 |
| `evidence_attribution` | Explainability | 4.30 |

This is no longer a chatbot return value. It is an **operational AI execution artifact**.

**Next step:** Step 4.31 — Inference vs Grounded-Fact Separation. Responses still do not explicitly distinguish directly grounded facts from inferred operational conclusions. That becomes the next major enterprise trust frontier: reasoning transparency governance.

---

## Step 4.31: Inference vs grounded-fact separation

**Category:** Reasoning Transparency Governance

**What:** Introduced explicit separation between directly grounded operational facts and inferred conclusions. The system now tracks what was directly extracted from evidence versus what was reasoned from combining lifecycle facts — making inference chains visible instead of blended into the response.

**The problem — blended facts and inference:**

The system produces "The payment was cancelled because auto-completion failed" but cannot distinguish: Was "auto-completion failed" explicitly retrieved? Or inferred from chronology? Or inferred from the combination of cancellation + processing failure? Currently facts and interpretation are blended into one response, creating hidden inference chains, audit ambiguity, support confusion, and over-trust in generated conclusions.

**Key principle:** Trustworthy systems must separate **evidence** from **interpretation**. Enterprise AI systems require inference transparency.

**What was built:**

**`app/core/rag/reasoning_separation.py`** — `separate_grounded_and_inferred_reasoning(lifecycle_facts, operational_evidence)`:

Two output categories:

**Grounded facts** (directly extracted from evidence):
- `intent_created` → "Intent creation succeeded"
- `processing_started` → "Processing started"
- `processing_failed` → "Processing failure detected"
- `transaction_cancelled` → "Transaction cancellation detected"

**Inferred conclusions** (reasoned from combining facts):
- `processing_failed + transaction_cancelled` → "Cancellation likely occurred after processing failure"
- `processing_started + !processing_failed + !final_state` → "Transaction may still be in progress"

**Example reasoning breakdown output:**
```json
{
  "grounded_facts": [
    "Intent creation succeeded",
    "Processing started",
    "Processing failure detected",
    "Transaction cancellation detected"
  ],
  "inferred_conclusions": [
    "Cancellation likely occurred after processing failure"
  ]
}
```

**Pipeline integration:**
- `retrieval_pipeline.py` — builds reasoning breakdown inside `process_retrieved_chunks()` after evidence attribution, includes in return dict
- `rag_pipeline.py` — extracts `reasoning_breakdown` from retrieval context
- `ExecutionResult` — expanded with `reasoning_breakdown: dict = {}`
- `run_eval.py` — optionally displays reasoning breakdown for debugging and reasoning audits

**What this enables:**

| Use case | How reasoning separation helps |
|----------|-------------------------------|
| Hallucination investigation | Check if conclusion was grounded or inferred |
| Support debugging | Know which claims are directly supported |
| Trust calibration | Weight grounded facts more than inferred conclusions |
| Reasoning audits | Trace inference chains explicitly |
| Regression analysis | Detect when inferred conclusions change across versions |

**Important design decisions:**
- **Operationally bounded:** NOT chain-of-thought exposure, NOT hidden reasoning dumps, NOT unrestricted internal traces. Only operationally relevant fact/inference separation
- **Deterministic:** Inference rules are explicit conditional logic, not LLM self-reflection
- **Internal telemetry:** Not yet exposed to end users — internal explainability for debugging and auditing

**What this step did NOT change:**
- No retrieval logic changes, no prompt changes
- Reasoning breakdown does not yet influence generation behavior or response constraints
- Inference rules are minimal — will expand as more lifecycle patterns are observed

**Next step:** Step 4.32 — Operational Ambiguity Detection. The system still does not explicitly detect insufficient evidence, multiple plausible explanations, unresolved operational ambiguity, or equally likely failure causes. That becomes the next major enterprise trustworthiness frontier: ambiguity-aware reasoning governance.

---

## Step 4.32: Operational ambiguity detection

**Category:** Uncertainty & Ambiguity Governance

**What:** Introduced ambiguity detection that identifies when retrieved evidence supports multiple plausible operational explanations without enough evidence to determine the primary root cause. This is fundamentally different from conflict detection (Step 4.28) — conflicts mean evidence contradicts; ambiguity means evidence supports multiple valid interpretations.

**The critical distinction:**

| State | Meaning | Example |
|-------|---------|---------|
| **Conflict** | Evidence contradicts itself | `completed` + `transaction_cancelled` |
| **Ambiguity** | Multiple plausible explanations coexist | `authentication issue` + `processing timeout` both present |

Without ambiguity governance, systems overcommit, hallucinate root causes, provide premature troubleshooting, and sound more certain than justified — dangerous in payment/compliance workflows.

**Key principle:** Reliable systems should acknowledge uncertainty explicitly, not hide ambiguity behind confident wording. Ambiguity handling should **calibrate certainty**, not destroy usefulness.

**What was built:**

**`app/core/rag/ambiguity_detection.py`** — `detect_operational_ambiguity(operational_evidence, operational_conflicts)`:

- Returns empty if operational conflicts already exist (conflicts take priority — different failure mode)
- Scans operational evidence text for co-occurring ambiguous pattern pairs:

| Pattern A | Pattern B | Ambiguity |
|-----------|-----------|-----------|
| authentication | processing | Unclear whether auth issue or processing failure |
| timeout | cancellation | Unclear whether timeout caused cancellation or vice versa |
| network | processing | Unclear whether network issue or processing failure |

- Returns list of ambiguity descriptions

**Pipeline and reliability integration:**
- `retrieval_pipeline.py` — detects ambiguities inside `process_retrieved_chunks()` after conflict detection, includes in return dict
- `response_reliability.py` — `compute_response_reliability()` now penalizes ambiguities (-10 per ambiguity), in addition to existing confidence/coherence/stability/conflict penalties
- `rag_pipeline.py` — extracts `operational_ambiguities`, feeds into reliability scoring
- `ExecutionResult` — expanded with `operational_ambiguities: list[str] = []`

**Updated reliability scoring (5 signals):**

| Signal | Max penalty | Step |
|--------|-------------|------|
| Low retrieval confidence | -40 | 4.29 |
| Weak lifecycle coherence | -25 | 4.29 |
| Low retrieval stability | -20 | 4.29 |
| Operational conflicts | -15 per conflict | 4.29 |
| **Operational ambiguities** | **-10 per ambiguity** | **4.32** |

Ambiguity penalty is lighter than conflict penalty — ambiguity reduces certainty, conflict invalidates reasoning.

**What this step did NOT change:**
- No retrieval logic changes, no prompt changes
- Ambiguity does not yet trigger specific response behavior (e.g., "multiple possible causes detected") — it feeds into reliability scoring which governs response mode
- Ambiguous patterns are minimal — will expand as more operational scenarios are observed

**Important — do NOT over-suppress on ambiguity:** Ambiguity handling should calibrate certainty, not force "I don't know" excessively or suppress useful troubleshooting. Some ambiguity is normal in operational support — the system should communicate uncertainty, not refuse to help.

---

**Phase 5 is now complete.** The system has evolved from response-text evaluation to full execution-level evaluation with retrieval benchmarking, lifecycle drift detection, adaptive retrieval with retry telemetry, quality comparison, stability analysis, coherence scoring, conflict detection, reliability-aware response downgrading, evidence attribution, reasoning separation, and ambiguity detection. Retrieval intelligence is no longer the bottleneck — the next phase (Phase 6 — Conversational Memory & Investigation Continuity) is documented in `5_conversational_memory.md`.
