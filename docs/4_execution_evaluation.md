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
