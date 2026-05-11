# Phase 4 — Knowledge Modeling & Retrieval Semantics

Continues from `2_normalization_and_distillation.md` (Phase 3: Structured Fact Extraction).

Step 3.7 (Evaluation Framework) exposed the real bottleneck: **retrieval taxonomy mismatch**. Flow domains, chunk topics, and eval domains use different naming conventions. Domain filtering breaks silently. The system has outgrown its metadata architecture.

This phase pauses all retrieval logic, prompt, eval, and sanitizer work. The foundation problem is **metadata architecture** — until that is fixed, every other optimization is unstable.

**Mental shift:** The system is no longer organizing *documents*. It is organizing **operational knowledge units**. That is a fundamentally different design challenge.

---

## Step 4.14: Contradiction detection & reasoning consistency

**Category:** Operational Reasoning Validation

**What:** Added a post-generation reasoning validator that checks the LLM's response against lifecycle facts for chronology contradictions and causal inconsistencies. The system now treats generated reasoning as **untrusted operational output** that must be validated before returning — not trusted LLM output that only needs cosmetic cleanup.

**The problem — reactive cleanup vs reasoning validation:**

Even with good retrieval, evidence attribution, and explicit timelines, the model can still produce inconsistent chronology ("intent creation failed after processing started"), unsupported causal chains, and logically invalid operational conclusions. The current defense is sanitization (regex-driven wording cleanup) — but regex only catches known patterns, cannot reason semantically, and cannot validate chronology logic. "Processing never started because completion failed" is logically invalid but no regex catches it.

**Key principle:** Sanitization should normalize wording. Reasoning validation is a separate subsystem. The system now has three distinct post-generation layers with different trust responsibilities.

**What was built:**

**`app/core/rag/reasoning_validator.py`** — `validate_reasoning_consistency(response, lifecycle_facts)`:

- **Chronology invariant:** If `processing_started = True`, then intent creation must have succeeded. Detects invalid patterns in response: "intent creation failed", "payment intent failed", "transaction creation failed"
- **Cancellation invariant:** If `transaction_cancelled = True`, cancellation must be downstream. Detects "cancelled before processing"
- Returns a list of `issues` — empty list means reasoning is consistent
- Intentionally deterministic — NOT another LLM, NOT self-reflection prompts, NOT recursive reasoning chains

**Pipeline integration — validation before sanitization:**

```python
response = generate_response(prompt)

reasoning_issues = validate_reasoning_consistency(
    response=response,
    lifecycle_facts=lifecycle_facts,
)

if reasoning_issues:
    logger.warning(f"Reasoning consistency issues: {reasoning_issues}")

response = sanitize_response(response)
return response
```

Validation runs on raw generated reasoning BEFORE sanitization — important because sanitization may hide evidence of bad reasoning. Currently issues are logged as warnings (not yet blocking), building observability before enforcement.

**The generation flow after this step:**

```
retrieval
→ governed generation (constraints, evidence, timeline)
→ reasoning validation (chronology/causal consistency check)
→ sanitization (wording normalization)
→ response
```

**Layered trust boundaries (emerging architecture pattern):**

| Layer | Trust level |
|-------|-------------|
| Retrieval metadata | High |
| Lifecycle facts | High |
| Operational evidence | High |
| Generated reasoning | Medium — requires validation |
| Unsupported inference | Low |

The system is starting to reflect enterprise trust boundaries — generation is no longer trusted output, it is validated output.

**What this step did NOT change:**
- No retrieval changes, no prompt changes, no context assembly changes
- Reasoning issues are currently logged, not used to block or regenerate (enforcement comes later)
- Validator rules are intentionally minimal — a few high-value operational invariants, not a giant rule engine

**Next step:** Step 4.15 — Confidence-Aware Response Behavior. The system computes `retrieval_confidence` but generation behavior still does not adapt to it — low-confidence retrieval still produces authoritative tone, strong causal claims, and overconfident operational explanations. That is the next major trustworthiness gap.

---

## Step 4.13: Lifecycle timeline reconstruction

**Category:** Explicit Operational Chronology Modeling

**What:** Added a deterministic timeline builder that reconstructs explicit operational event order from lifecycle facts before generation. The model no longer infers chronology from fragmented evidence chunks — it receives a numbered, ordered timeline of what happened. Chronology becomes **retrieval-governed** instead of LLM-inferred.

**The problem — implicit chronology from fragments:**

Lifecycle facts (`processing_started = True`, `transaction_cancelled = True`) are state indicators, not event chronology. Retrieved chunks may contain "intent created", "processing started", "auto-completion failed", "transaction cancelled" — but the temporal order is still implicit. The model must reconstruct the timeline itself, which creates chronology drift, causal hallucinations, lifecycle confusion, and inconsistent explanations, especially in edge cases.

**Key principle:** LLMs are weak at reconstructing precise operational timelines from fragmented evidence. The retrieval layer should reconstruct chronology BEFORE generation.

**What was built:**

**`app/core/rag/timeline_builder.py`** — `build_lifecycle_timeline(lifecycle_facts)`:
- Deterministic, ordered event construction from lifecycle facts:
  1. `intent_created` → "Payment intent was created."
  2. `processing_started` → "Payment processing started."
  3. `processing_failed` → "Payment processing failed."
  4. `transaction_cancelled` → "Transaction was cancelled."
  5. `final_state` → "Final transaction state: {state}."
- Intentionally NOT LLM-generated, NOT chain-of-thought, NOT inferential — deterministic only

**Example timeline the model now receives:**
```
LIFECYCLE_TIMELINE:
1. Payment intent was created.
2. Payment processing started.
3. Payment processing failed.
4. Transaction was cancelled.
5. Final transaction state: cancelled.
```

**Pipeline integration:**
- `retrieval_pipeline.py` — builds timeline from `final_lifecycle_facts` after operational evidence, returns `lifecycle_timeline` in context dict
- `rag_pipeline.py` — extracts timeline, passes to context builder
- `context_builder.py` — accepts `lifecycle_timeline` parameter, builds numbered `LIFECYCLE_TIMELINE` section placed between `OPERATIONAL_EVIDENCE` and `LIFECYCLE_CONTEXT`

**Context section ordering (what the model now sees):**
1. `OPERATIONAL_EVIDENCE` — grounded facts
2. `LIFECYCLE_TIMELINE` — explicit chronology
3. `LIFECYCLE_CONTEXT` — operational/business rule chunks with evidence IDs
4. `TROUBLESHOOTING_CONTEXT` — troubleshooting chunks
5. `TRANSPORT_CONTEXT` — transport chunks (deprioritized)

**What this changes architecturally:**

| Before | After |
|--------|-------|
| Model infers chronology from fragmented evidence blobs | Model receives explicit operational event order |
| Timeline reconstruction happens during generation | Timeline reconstruction happens in retrieval layer |
| Chronology drift in edge cases | Deterministic chronology from lifecycle facts |

**Expected effects (without changing prompts):**
- Chronology reasoning stabilizes massively
- Cancellation explanations improve heavily (clear cause → outcome ordering)
- Causal hallucinations and lifecycle contradictions drop sharply
- Operational explanations become more deterministic

**What this step did NOT change:**
- No retrieval changes, no scoring changes, no model changes
- Timeline is currently derived from lifecycle facts only — not yet from chunk-level event ordering (future evolution)

**Next step:** Step 4.14 — Contradiction Detection & Reasoning Consistency Checks. The system should actively detect inconsistent lifecycle reasoning, unsupported causal chains, chronology violations, and conflicting operational claims before returning the answer — moving beyond relying on prompt constraints and sanitization alone.

---

## Step 4.12: Evidence attribution & claim grounding

**Category:** Explicit Reasoning Grounding

**What:** Added stable evidence identifiers (`EV_001`, `EV_002`, ...) to every context chunk, enriched each evidence block with `KNOWLEDGE_TYPE` metadata, and added explicit grounding policy to both response constraints and the prompt template. The model no longer receives anonymous context blobs — it receives **structured evidence units** with identifiers, enabling traceable operational reasoning.

**The problem — untraceable conclusions:**

The system produces operational explanations, lifecycle reasoning, and cancellation analysis. But the response does not explicitly ground which evidence supported which conclusion, which lifecycle fact enabled which inference, or which operational chunk justified which claim. If the model says "the payment was cancelled because auto-completion failed," there is no way to verify whether that was directly grounded in evidence or silently inferred across gaps. That creates weak traceability, hidden hallucination risk, hard-to-debug reasoning, and poor enterprise trustworthiness.

**Key principle:** The model should NOT silently bridge evidence gaps. Operational conclusions should explicitly reference supporting evidence. This is NOT customer-visible citations — it is **internal reasoning grounding**.

**What was changed — three components:**

1. **`app/core/rag/context_builder.py`** — Each chunk now gets an `EVIDENCE_ID` and `KNOWLEDGE_TYPE`:

```
EVIDENCE_ID: EV_001
CAPABILITY: create_intent
LIFECYCLE_STAGE: cancellation
KNOWLEDGE_TYPE: operational_behavior
CONTENT:
Payment cancellation occurs after...
```

Previously chunks were anonymous text blocks with only `CAPABILITY`, `LIFECYCLE_STAGE`, and `CONTENT`. Now the model sees structured evidence units with stable identifiers it can reason about.

2. **`app/core/rag/response_governance.py`** — Added grounding constraint:
   - `"Operational conclusions must align with provided evidence."` added to base constraints alongside existing "Do not invent operational causes"

3. **`app/utils/prompts.py`** — Added explicit grounding policy to `PROMPT_TEMPLATE`:
   - `"All operational conclusions must be grounded in the provided evidence context."` and `"Do not infer unsupported operational causes."` placed in the `RESPONSE_CONSTRAINTS` section, before the context — grounding policy shapes generation before evidence is seen

**The architectural transition:**

| Before | After |
|--------|-------|
| Context-assisted generation (anonymous text blobs) | Evidence-governed reasoning (structured evidence units with IDs) |
| Model silently bridges evidence gaps | Model receives grounding policy + identifiable evidence |
| Conclusions are untraceable | Conclusions become auditable against evidence IDs |

**What evidence IDs enable long-term:**
- Hallucination debugging: trace which evidence the model used vs invented
- Contradiction detection: verify claims against specific evidence blocks
- Auditability: enterprise compliance requires reasoning traceability
- Future citation: evidence IDs can eventually surface in responses if needed

**What this step did NOT change:**
- No retrieval changes, no scoring changes, no confidence changes
- Evidence IDs are internal (not yet surfaced to users)
- The model is not yet forced to cite evidence IDs in responses — that is a future constraint

**Next step:** Step 4.13 — Lifecycle Timeline Reconstruction. Instead of the model inferring chronology from chunks, the retrieval layer explicitly reconstructs operational event order, causality chains, lifecycle transitions, and failure propagation. One of the biggest remaining reasoning-quality improvements.

---

## Step 4.11: Response constraint governance

**Category:** Controlled Operational Generation

**What:** Introduced a response governance layer that injects structured operational constraints into generation based on retrieval confidence and lifecycle facts. The model no longer receives "here is evidence, generate an answer." It now receives "generate ONLY within operationally-allowed boundaries." This is **operational policy injection**, not prompt engineering.

**The problem — unconstrained generation freedom:**

Even with good retrieval, LLMs naturally over-generalize, over-infer, sound overconfident, and invent causal bridges. If retrieval evidence says "processing failed after intent creation," the model may still say "the payment failed because the webhook was not received" — even if webhook evidence was weak, webhook causality was not proven, and only transport chunks implied it indirectly. That is **causal hallucination**, very common in enterprise RAG. Most hallucinations are not "bad retrieval" — they are unconstrained generation behavior.

**Key principle:** The model should NOT decide what operational claims are allowed. That belongs to **response governance**, not freeform generation.

**What was built:**

**`app/core/rag/response_governance.py`** — `build_response_constraints(retrieval_confidence, lifecycle_facts)`:

Three constraint categories:

1. **Base constraints** (always applied):
   - Do not invent operational causes
   - Do not infer unsupported webhook failures
   - Do not assume transport-layer failures
   - Do not mix lifecycle stages
   - Do not describe intent creation failure after processing started

2. **Confidence-aware constraints** (when `retrieval_confidence < 0.40`):
   - Use cautious phrasing
   - Avoid definitive root-cause claims
   - State when evidence is incomplete

3. **Lifecycle-aware constraints** (conditional on facts):
   - If `processing_started`: "Intent creation already succeeded"
   - If `transaction_cancelled`: "Cancellation must be treated as a downstream result"

**Pipeline integration:**
- `rag_pipeline.py` — computes constraints after retrieving confidence and lifecycle facts, passes them to prompt builder
- `prompt.py` — `build_prompt_with_step()` now accepts `response_constraints` and injects them as a `RESPONSE_CONSTRAINTS` section **before** the context — constraints shape generation before evidence

**The architectural shift:**

| Before | After |
|--------|-------|
| retrieval → prompt → answer | retrieval → evidence validation → confidence estimation → operational policy injection → controlled generation |

This also reduces prompt overfitting. Previously, reactive prompt patches like "don't say intent creation failed" and "don't mention webhooks" accumulated as ad-hoc rules. Now those become structured operational constraints — cleaner and more scalable.

**Important — constraints must stay focused:** Do NOT turn constraints into 100-rule mega prompts. Constraints should remain operational, lifecycle-focused, policy-oriented, high-signal. Not giant prompt patch collections. That lesson was already learned in earlier phases.

**What this step did NOT change:**
- No retrieval changes, no embedding changes
- Constraints are injected into prompts but generation behavior is not yet branched by confidence level (full confidence-driven behavior comes later)

**Next step:** Step 4.12 — Evidence Attribution & Citation Grounding. The model still generates freeform operational explanations without explicitly grounding which evidence supported which claim, which lifecycle facts drove reasoning, and which operational chunks justified conclusions. That is the next major controllability and trustworthiness evolution.

---

## Step 4.10: Retrieval confidence modeling

**Category:** Evidence Confidence Governance

**What:** Introduced retrieval confidence scoring — the system now estimates how strong, complete, and trustworthy the retrieved evidence is **before** generation. This is NOT AI confidence (model self-assessment). It is **retrieval evidence confidence** — a governance-layer estimation based on chunk count, lifecycle diversity, operational knowledge quality, and lifecycle fact completeness. Critical distinction.

**The problem — no distinction between strong and weak retrieval:**

After Step 4.8 (validation), the pipeline gates generation on evidence sufficiency. But if retrieval barely passes validation — e.g., 2 weak chunks, partial lifecycle evidence, fragmented operational states — generation proceeds exactly the same as with strong evidence, high-confidence lifecycle grounding, and complete operational chronology. The model produces high-confidence operational explanations regardless of evidence quality. That creates **overconfident hallucinations** — authoritative-sounding answers built on weak evidence. One of the biggest enterprise RAG risks.

**Key principle:** LLMs should NOT decide whether they are confident. That belongs to **retrieval governance**, not generation.

**What was built:**

**`app/core/rag/retrieval_confidence.py`** — `compute_retrieval_confidence(selected_chunks, lifecycle_facts)`:

| Signal | Score | Why |
|--------|-------|-----|
| >= 5 chunks | +0.30 | Strong evidence volume |
| >= 3 chunks | +0.20 | Moderate evidence |
| >= 2 chunks | +0.10 | Minimum evidence |
| >= 2 lifecycle stages | +0.25 | Lifecycle diversity (chronology coverage) |
| >= 2 operational knowledge types | +0.25 | Reasoning quality (not just one type of evidence) |
| `processing_failed` detected | +0.10 | Failure reasoning grounding |
| `transaction_cancelled` detected | +0.10 | Cancellation reasoning grounding |
| Maximum | 1.0 | Capped |

**Pipeline integration:**
- `retrieval_pipeline.py` — computes confidence after final lifecycle extraction and validation, returns `retrieval_confidence` in the context dict
- `rag_pipeline.py` — retrieves confidence score (temporarily logged, not yet exposed to users or used for behavior control)

**Pipeline position (after validation, before distillation):**

```
→ final lifecycle extraction
→ retrieval validation (sufficiency gate)
→ retrieval confidence (quality estimation)
→ distillation
→ operational evidence
```

Validation answers: "Can generation proceed?" Confidence answers: "How trustworthy is the evidence?" Different layers.

**Future value — confidence-driven behavior:**

| Confidence | Behavior |
|------------|----------|
| High | Full operational reasoning |
| Medium | Cautious explanations |
| Low | Constrained/fallback answers |
| Very low | Escalation / insufficient evidence response |

This becomes foundational for safe enterprise AI behavior — escalation logic, fallback responses, and uncertainty handling all depend on confidence infrastructure existing first.

**Important — do NOT obsess over exact weights yet:** The specific numbers (0.25, 0.30, 0.10) are not sacred. The architecture matters more than the exact scoring at this stage. Tuning comes later with eval data.

**What this step did NOT change:**
- No prompt changes, no retrieval changes, no generation behavior changes yet
- Confidence is computed and logged but not yet used to modify generation behavior
- Not exposed to users — premature until behavior policies are defined

**Next step:** Step 4.11 — Response Constraint Governance. The model still has too much freedom in answer structure, operational assertions, chronology phrasing, and causal explanation style. That is the next major controllability layer.

---

## Step 4.9: Context assembly governance

**Category:** Structured Evidence Grounding

**What:** Replaced semi-freeform chunk concatenation in `rag_pipeline.py` with a dedicated context builder (`app/core/rag/context_builder.py`) that structures generation context into typed evidence sections. The model no longer receives flat text blobs where it must infer importance, causality, and evidence hierarchy. It now receives **pre-structured operational evidence packaging**.

**The problem — flat context concatenation:**

After all the retrieval infrastructure improvements (metadata, lifecycle scoring, observability, validation), context assembly was still:

```
raw_context = "\n\n".join(normalized_chunks)
context = f"OPERATIONAL_EVIDENCE:\n{evidence_block}\n\nSUPPORTING_CONTEXT:\n{raw_context}"
```

All retrieved evidence entered generation as equal-looking text. A critical processing failure chunk, a high-importance cancellation result, a low-value webhook retry note, and a medium polling fallback all competed equally in `SUPPORTING_CONTEXT`. The model itself had to decide what matters most — weak architecture. LLMs are much better at reasoning over structured evidence than sorting noisy evidence themselves.

**What was built:**

**`app/core/rag/context_builder.py`** — `build_structured_context(context_chunks, operational_evidence)`:
- Classifies each chunk by `knowledge_type` into typed sections:
  - `operational_behavior` / `business_rule` → `LIFECYCLE_CONTEXT`
  - `troubleshooting` → `TROUBLESHOOTING_CONTEXT`
  - `transport_behavior` → `TRANSPORT_CONTEXT`
- Each chunk entry includes explicit `CAPABILITY` and `LIFECYCLE_STAGE` headers — the model sees structured metadata, not raw text
- Assembles sections in priority order: `OPERATIONAL_EVIDENCE` → `LIFECYCLE_CONTEXT` → `TROUBLESHOOTING_CONTEXT` → `TRANSPORT_CONTEXT`
- Empty sections are omitted entirely — no noise

**Context structure the model now receives:**

```
OPERATIONAL_EVIDENCE:
- payment intent creation succeeded
- processing started
- auto-completion failed
- transaction cancelled after processing failure

LIFECYCLE_CONTEXT:

CAPABILITY: create_intent
LIFECYCLE_STAGE: auto_completion
CONTENT:
<operational chunk text>

TROUBLESHOOTING_CONTEXT:

CAPABILITY: create_intent
LIFECYCLE_STAGE: cancellation
CONTENT:
<troubleshooting chunk text>
```

Previously all of this was a single `SUPPORTING_CONTEXT` blob.

**`rag_pipeline.py` simplified:** The entire manual context assembly block (normalized_chunks loop, regex replacements, topic/tag formatting, raw_context concatenation) was deleted. Replaced with a single call:

```python
context = build_structured_context(
    context_chunks=distilled_chunks,
    operational_evidence=operational_evidence
)
```

`rag_pipeline.py` now cleanly follows its intended role — high-level orchestration only:
1. Retrieval orchestration → 2. Diagnostic check → 3. Structured context assembly → 4. Prompt generation → 5. LLM response → 6. Sanitization

**The architectural transition:** The system is moving from **retrieval-guided prompting** to **evidence-governed generation**. The retrieval layer now structures evidence before generation, instead of dumping raw chunks and hoping the prompt sorts it out.

**Expected effects (without changing prompts):**
- Better chronology consistency, less cancellation confusion
- Cleaner operational explanations, less transport leakage
- Less prompt overfitting pressure — the model receives pre-organized evidence

**Long-term importance:** The context builder eventually becomes responsible for chronology ordering, evidence prioritization, token budgeting, contradiction suppression, and confidence-aware packaging. Most enterprise RAG systems never separate this layer cleanly — it stays buried in prompt assembly forever.

**What this step did NOT change:**
- No prompt changes, no retrieval changes, no model changes
- Transport sections still included (just deprioritized by section ordering) — full suppression comes later

---

## Step 4.8: Retrieval quality validation + lifecycle extraction ordering fix

**Category:** Retrieval Evidence Validation

**What:** Introduced an evidence sufficiency gate that validates retrieval quality before generation. The system no longer assumes "retrieval returned chunks = enough evidence." It now enforces **evidence sufficiency contracts** — minimum chunk count, required lifecycle evidence, required operational knowledge types. Also fixed a subtle lifecycle extraction ordering bug where validation was running against stale lifecycle facts.

**The problem — retrieval existence != retrieval sufficiency:**

If retrieval returns 2 weak chunks with partial lifecycle evidence and fragmented operational states, the generation layer previously proceeded normally. That creates weak reasoning, vague answers, low-confidence operational explanations, and hallucinated lifecycle transitions. The pipeline validated retrieval *existence* (`if not selected_chunks`) but not retrieval *sufficiency*. Hallucinations are often not "model intelligence failures" — they are **retrieval sufficiency failures**. Fundamental enterprise RAG principle.

**What was built:**

**`app/core/rag/retrieval_validator.py`** — `validate_retrieval_quality(selected_chunks, lifecycle_facts)`:
- Minimum evidence count: requires >= 2 selected chunks
- Lifecycle evidence validation: if `lifecycle_facts.transaction_cancelled` is true, requires `"cancellation"` in chunk lifecycle stages — blocks generation when cancellation evidence was claimed but no cancellation chunk survived selection
- Operational knowledge type validation: requires at least one chunk of type `operational_behavior`, `troubleshooting`, or `business_rule` — blocks generation when only transport/payload chunks remain
- Returns `(is_valid, validation_reason)` — reason feeds into diagnostics

**Evidence sufficiency contracts:**

| Requirement | Why |
|-------------|-----|
| >= 2 chunks | Prevent single-source hallucination |
| Lifecycle evidence matches lifecycle facts | Prevent disconnected reasoning |
| Operational knowledge types present | Prevent transport-only generation |

**The lifecycle extraction ordering bug:**

The pipeline has two lifecycle extractions that serve different purposes:

| Extraction | Input | Purpose |
|------------|-------|---------|
| Initial | `candidate_chunks` (broad) | Guide lifecycle-aware chunk selection |
| Final | `selected_chunks` (refined) | Validate and ground final evidence for generation |

The bug: validation was running against the **initial** lifecycle facts (extracted from broad candidates) instead of the **final** lifecycle facts (extracted from selected chunks). This meant validation could believe `transaction_cancelled = True` from the initial extraction, but the actual cancellation chunk may have been removed during selection. Validation was disconnected from final evidence.

**The fix:** Moved final lifecycle extraction **before** validation:

```
candidate_chunks
→ initial lifecycle extraction (guides selection)
→ lifecycle chunk selection
→ LLM selection
→ FINAL lifecycle extraction (on selected_chunks)
→ retrieval validation (using final facts)
→ distillation
→ operational evidence (using final facts)
```

**Recommended cleanup (variable naming):** Rename the two `lifecycle_facts` variables to `initial_lifecycle_facts` (for selection guidance) and `final_lifecycle_facts` (for validation + evidence) to make the semantic distinction explicit.

**Pipeline integration:** Validation failure records in diagnostics as `failed_stage: "retrieval_validation"` with the specific reason (`insufficient_chunk_count`, `missing_cancellation_evidence`, `missing_operational_evidence`). Returns early with diagnostic — generation never runs on insufficient evidence.

**Key architectural principle:** The generation layer should NEVER decide whether evidence is sufficient. That belongs to **retrieval governance**. Generation receives pre-validated evidence or doesn't run at all.

**Expected effects:**
- Hallucination pressure drops massively — model no longer generates on incomplete chronology
- Cancellation reasoning improves — can't proceed without cancellation evidence
- Retrieval quality becomes enforceable, not just observable

**What this step did NOT change:**
- No prompt changes, no embedding changes, no model changes
- Validation rules are intentionally conservative — can be tightened later using eval data

**Current pipeline state — fully observable operational retrieval orchestration:**

| Stage | File | Purpose |
|-------|------|---------|
| Vector search | `retriever.py` | Embedding similarity retrieval |
| Structured filtering | `retrieval_filtering.py` | Metadata-governed filtering + trace |
| Noise suppression | `retrieval_rules.py` | Infra-noise removal |
| Initial lifecycle extraction | `lifecycle_extractor.py` | Broad operational state (guides selection) |
| Lifecycle chunk selection | `lifecycle_chunk_selector.py` | Chronology-coherent prioritization |
| LLM chunk refinement | `chunk_selector.py` | Secondary semantic refinement |
| Final lifecycle extraction | `lifecycle_extractor.py` | Final operational grounding |
| Retrieval validation | `retrieval_validator.py` | Evidence sufficiency gate |
| Distillation | `operational_distiller.py` | Implementation noise removal |
| Operational evidence | `operational_evidence.py` | Explicit grounding statements |

**Next step:** Step 4.9 — Context Assembly Governance. Currently prompt context assembly is still semi-freeform chunk concatenation. Context itself must become structured, lifecycle-segmented, evidence-prioritized, and chronology-aware — where generation quality jumps again without prompt overfitting.

---

## Step 4.7: Retrieval failure classification & staged pipeline observability

**Category:** Retrieval Infrastructure Engineering

**What:** Transformed the retrieval pipeline from opaque execution (chunks in, chunks out, "No relevant context found" on failure) into **observable staged retrieval execution** where every stage tracks chunk counts, collapse points are identified automatically, and retrieval failures are classified by the stage that caused them.

**The problem — silent retrieval collapse:**

Before this step, every pipeline stage only returned chunks. If any stage accidentally removed everything, downstream stages silently received empty input and the user saw "No relevant context found" — with zero visibility into whether vector search failed, filtering was too aggressive, noise suppression over-pruned, lifecycle selection collapsed, or LLM refinement removed all context. Debugging was print statements + guessing. Not production-grade.

**What was built:**

1. **`app/core/rag/retrieval_diagnostics.py`** — Structured diagnostic models:
   - `RetrievalDiagnostic` — tracks `failed_stage`, `reason`, and `chunk_counts` (per-stage survival counts)
   - `RetrievalStage` — enum: `VECTOR_SEARCH`, `STRUCTURED_FILTERING`, `NOISE_SUPPRESSION`, `LIFECYCLE_SELECTION`, `LLM_SELECTION`, `DISTILLATION`

2. **`app/core/rag/retrieval_pipeline.py`** — Rewritten with per-stage diagnostics:
   - Every stage records its chunk count in `diagnostic.chunk_counts`
   - Every stage checks for empty results and records the collapse point with a human-readable reason
   - On failure, returns early with `{ "diagnostic": diagnostic }` — no more silent `None`
   - On success, returns the full context plus the diagnostic

**Diagnostic output example:**
```json
{
  "failed_stage": "llm_selection",
  "reason": "All chunks removed by select_relevant_chunks",
  "chunk_counts": {
    "vector_search": 8,
    "structured_filtering": 5,
    "noise_suppression": 4,
    "lifecycle_selection": 3,
    "llm_selection": 0
  }
}
```

Now you can instantly see where retrieval collapsed, which stage over-filtered, and whether the problem is metadata, scoring, or semantic refinement.

**The 8-stage retrieval pipeline (now fully observable):**

| Stage | Purpose | What it answers |
|-------|---------|-----------------|
| 1. Vector search | Embedding similarity retrieval | "What does similarity think is relevant?" |
| 2. Structured filtering | Metadata-governed filtering (capability, lifecycle, visibility, knowledge type) | "What survives domain contracts?" |
| 3. Noise suppression | Remove infra-noise chunks | "What survives quality filtering?" |
| 4. Lifecycle extraction | Infer operational chronology from evidence | "What is the operational state?" |
| 5. Lifecycle chunk selection | Prioritize chronology-coherent chunks | "What best explains the lifecycle?" |
| 6. LLM chunk refinement | Secondary semantic refinement | "What is semantically focused?" |
| 7. Distillation | Compress implementation noise | "What is operationally clean?" |
| 8. Operational evidence | Generate explicit grounding statements | "What are the grounded facts?" |

**Before vs after:**
- Before: `"No relevant context found"` — opaque failure, no execution history
- After: `"Retrieval collapsed during LLM refinement — 8 chunks entered, 5 survived filtering, 3 survived selection, 0 after LLM refinement"` — self-describing execution

**Other structural improvements in this stage:**

- **Circular dependency fix:** Extracted `lifecycle_extractor.py` and `retrieval_rules.py` into independent modules to break the `rag_pipeline ↔ retrieval_pipeline` circular import
- **Retrieval stage isolation:** `build_retrieval_context()` is now a clean orchestration layer with each subsystem (filtering, selection, extraction, distillation, evidence) as isolated modules with clear boundaries
- **`rag_pipeline.py` simplified:** High-level orchestration only — delegates retrieval to `build_retrieval_context()`, handles context assembly, prompt building, generation, and sanitization

**The architectural evolution:**
- Before this stage: semantic retrieval + prompting
- After this stage: **staged operational retrieval infrastructure** — observable, diagnosable, traceable

**What this stage did NOT change:**
- No embedding improvements, no semantic similarity changes, no prompt tuning, no model changes
- This was **retrieval infrastructure engineering**, not AI quality tuning

**Key outcome:** Future improvements become measurable, diagnosable, and traceable instead of "try prompt changes and hope." This is one of the biggest maturity jumps the system has made — the transition from advanced RAG experimentation to diagnosable AI infrastructure.

---

## Step 4.6: Lifecycle-aware chunk selection

**Category:** Operational Chronology Selection

**What:** Changed chunk selection from "which chunks are semantically relevant?" to "which chunks best explain the operational lifecycle?" The system now has a deterministic lifecycle-aware selection layer that runs before the LLM-based semantic selector, making operational chronology the primary selection criteria instead of embedding similarity.

**The problem — selector is still semantically oriented:**

Even though retrieval became lifecycle-aware (Step 4.4) and metadata became structured (Steps 4.1-4.3), the final chunk selection layer still behaved like semantic relevance compression. For "why was payment cancelled?", the semantic selector might choose webhook cancellation payloads, socket event schemas, and rollback mechanics (high embedding similarity because "cancelled" appears frequently) instead of the operationally needed processing chronology, failure cause, and cancellation outcome.

**Core principle:** For this system, **chronology coherence matters more than semantic density**.

**What was built — two new files:**

1. **`app/core/rag/chunk_selection_policy.py`** — `compute_chunk_selection_score(chunk, lifecycle_facts)`:
   - Knowledge type scoring: `operational_behavior` +3, `troubleshooting` +2, `transport_behavior` -3
   - Lifecycle alignment scoring (uses extracted `lifecycle_facts` to boost contextually relevant chunks):
     - `final_state == "cancelled"` + chunk stage is `cancellation` → +4
     - `processing_failed` + chunk state is `failed` → +3
     - `processing_completed` + chunk state is `completed` → +2
   - Deterministic, no LLM, no summarization, no chain-of-thought

2. **`app/core/rag/lifecycle_chunk_selector.py`** — `select_lifecycle_chunks(filtered_chunks, lifecycle_facts, top_k=5)`:
   - Rescores each chunk: `final_score = retrieval_score + policy_score`
   - Sorts by final score, returns top_k
   - Explicitly does NOT use LLMs, summarize, reason recursively, or generate chains

**Key architecture shift — pipeline ordering changed:**

The selection flow in `retrieval_pipeline.py` was restructured. Lifecycle extraction now happens **before** chunk selection refinement:

```
vector retrieval
→ structured filtering + trace
→ noise suppression
→ lifecycle extraction (first pass)
→ lifecycle-aware chunk selection (new — primary)
→ LLM semantic chunk selection (existing — secondary refinement)
→ lifecycle extraction (second pass — on final selected chunks)
→ distillation
→ operational evidence
```

Previously lifecycle extraction happened after selection. Now it informs selection — the selector knows whether the transaction was cancelled, failed, or completed, and boosts chunks that explain that outcome.

**Design decision — LLM selector becomes secondary:**

The existing LLM-based `select_relevant_chunks()` was not deleted. It now runs after lifecycle-aware selection as a secondary semantic refinement pass, not the primary operational selector. This is intentional — lifecycle policy controls what gets selected, LLM selector refines within that.

**Design decision — do NOT over-compress:**

`top_k=5` is intentionally generous. The system still benefits from supporting operational nuance, contextual edge cases, and fallback evidence. Over-compression too early causes robotic answers, brittle reasoning, and missing edge-case handling.

**Expected effects (without changing prompts):**
- More coherent cancellation explanations, better chronology preservation
- Fewer transport-heavy chunks in final selection
- Cleaner operational evidence, better eval consistency
- More stable answers across query variations

**What this step did NOT change:**
- No prompt changes, no embedding changes
- LLM chunk selector still exists as secondary refinement
- Score values (3, 4, -3) are not tuned yet — retrieval semantics infrastructure first, tuning via evals later

**Next step:** Step 4.7 — Retrieval Failure Classification. The system begins understanding WHY retrieval failed (no capability match, lifecycle mismatch, over-filtering, metadata inconsistency, transport suppression removed all evidence) — moving toward self-diagnosing retrieval infrastructure.

---

## Step 4.5: Retrieval observability & diagnostics

**Category:** LLMOps Retrieval Visibility

**What:** Made retrieval **explainable** by introducing structured retrieval trace objects. Every filtering/scoring decision is now recorded — why a chunk was retrieved, why it was suppressed, what scores contributed to its ranking. Replaced ad-hoc `print()` debugging with inspectable infrastructure.

**The problem — debugging retrieval blind:**

The system can now retrieve, filter, score, and suppress. But when retrieval fails or produces unexpected results, the only debugging available was reading scattered print statements. That does not scale. The system is no longer "semantic search" — it is **retrieval policy infrastructure**, and policy decisions need visibility.

**What observability answers:**

| Question | Trace provides |
|----------|---------------|
| Why was this chunk retrieved? | lifecycle boost, knowledge type score |
| Why was this chunk suppressed? | `exclusion_reason`: internal_visibility, capability_mismatch |
| Why was retrieval empty? | All decisions show `included: false` with reasons |
| Why did irrelevant chunks dominate? | `score_breakdown` reveals weak metadata |
| Why did cancellation reasoning fail? | lifecycle_stage mismatch visible in trace |

**What was built — three components:**

1. **`app/core/rag/retrieval_trace.py`** — Structured trace models:
   - `RetrievalDecision` — per-chunk record: `chunk_id`, `capability`, `lifecycle_stage`, `knowledge_type`, `importance`, `base_score`, `adjusted_score`, `included`, `exclusion_reason`, `score_breakdown`
   - `RetrievalTrace` — query-level record: `query`, `step_domain`, `step_topic`, list of all `decisions`

2. **`app/core/rag/retrieval_filtering.py`** — Updated to collect trace alongside filtering:
   - `apply_structured_filters()` now returns `(filtered_chunks, trace)` instead of just `filtered_chunks`
   - Every chunk processed creates a `RetrievalDecision` with full score breakdown
   - Excluded chunks record their `exclusion_reason` (`"internal_visibility"`, capability mismatch, etc.)
   - Included chunks record `score_breakdown`: `{ lifecycle_score, knowledge_score, importance_score }`

3. **`app/core/rag/retrieval_debugger.py`** — Diagnostic logger:
   - `print_retrieval_trace(trace)` — prints structured trace for every chunk decision (capability, stage, type, base/adjusted scores, breakdown, exclusion reason)
   - Currently called temporarily from `rag_pipeline.py` after retrieval — will become structured logging later

**Pipeline integration:**
- `retrieval_pipeline.py` — unpacks `(filtered, retrieval_trace)` from filtering, passes `retrieval_trace` in the return dict
- `rag_pipeline.py` — extracts `retrieval_trace` from context, calls `print_retrieval_trace()` for temporary visibility

**Updated responsibility boundaries:**

| Layer | File | Responsibility |
|-------|------|----------------|
| Metadata access | `retrieval_metadata.py` | Schema abstraction |
| Retrieval filtering | `retrieval_filtering.py` | Metadata semantics, suppression, boosting, trace collection |
| Retrieval tracing | `retrieval_trace.py` | Structured decision records |
| Retrieval debugging | `retrieval_debugger.py` | Diagnostic output |
| Retrieval orchestration | `retrieval_pipeline.py` | Retrieval grounding pipeline |
| Noise suppression | `retrieval_rules.py` | Noise chunk rules |
| Lifecycle extraction | `lifecycle_extractor.py` | Deterministic lifecycle grounding |
| Lifecycle state | `lifecycle_facts.py` | Normalized lifecycle model |
| Operational abstraction | `operational_distiller.py` | Infra-noise reduction |
| Explicit grounding | `operational_evidence.py` | Evidence statements |
| Generation constraints | `prompt.py` | Prompt governance |
| High-level orchestration | `rag_pipeline.py` | Retrieve → prompt → generate → sanitize |

**Key architectural transition:** Retrieval is now **inspectable infrastructure** instead of "whatever vector search returned." This is foundational for eval debugging, ranking tuning, taxonomy tuning, failure analysis, and lifecycle retrieval debugging. Without observability, all tuning is blind.

**Important — structured diagnostics, not logging spam:** The trace captures policy decisions (inclusion/exclusion + reasons + score breakdowns), not raw data dumps. That distinction is what separates production observability from prototype print statements.

**What this step did NOT change:**
- No retrieval logic changes, no scoring changes, no prompt changes
- Debug output is temporary (print-based) — will evolve into structured logging
- Trace is collected but not yet persisted or exposed via API

**Next step:** Step 4.6 — Lifecycle-Aware Chunk Selection. The LLM chunk selector is currently still a semantic relevance selector. It must become an **operational chronology selector** — the next major retrieval evolution.

---

## Step 4.4: Lifecycle-aware retrieval scoring

**Category:** Operational Retrieval Intelligence

**What:** Evolved the retrieval filtering layer from hard filtering + lightweight boosts into an intelligent, multi-signal operational scoring engine. Retrieval ranking itself now understands lifecycle stages, knowledge types, and importance — not just embedding similarity. This is the transition from **semantic similarity search** to **operationally-prioritized retrieval**.

**The problem — retrieval scoring is too shallow:**

After Step 4.3, retrieval filtering was structured and metadata-driven, but scoring was still primitive: a single +0.35 boost for exact lifecycle stage match and a -0.25 penalty for transport chunks. That meant a chunk could still rank highly because wording is similar or embeddings are close, even if the lifecycle stage is wrong, the operational state is irrelevant, or the mechanism dominates. Example: "why was payment cancelled?" could retrieve webhook cancellation payload docs, socket events, and rollback schemas (semantically similar because "cancelled" appears frequently) instead of the operationally needed cancellation cause, processing failure chronology, and auto-completion semantics.

**Core principle for this system:** Lifecycle relevance matters more than semantic similarity.

**What was built — three scoring functions added to `retrieval_filtering.py`:**

1. **`compute_lifecycle_score(chunk_stage, step_topic)`** — Chronology-aware lifecycle scoring:
   - Exact stage match → +0.45
   - Related stage match → +0.20 (e.g., `auto_completion` step also boosts `completion`, `cancellation`, `settlement` chunks)
   - Related stage mappings defined per capability (`auto_completion`, `payment_status`, `platform_transaction`)
   - No match → 0

2. **`compute_knowledge_type_score(knowledge_type)`** — Operational usefulness scoring:
   - `operational_behavior` → +0.30
   - `troubleshooting` → +0.25
   - `business_rule` → +0.20
   - `integration_guidance` → +0.15
   - `transport_behavior` → -0.35
   - `payload_schema` → -0.40
   - This formalizes: operational chunks > transport chunks (previously only weakly suppressed)

3. **`compute_importance_score(importance)`** — Metadata-driven priority weighting:
   - `critical` → +0.30, `high` → +0.20, `medium` → +0.10, `low` → 0

**Updated `apply_structured_filters()` — composite scoring:**

The previous simplistic boost was replaced with a composite score:
```
adjusted_score = base_similarity + lifecycle_score + knowledge_score + importance_score
```

Debug output now shows the full scoring breakdown: `adjusted_score | base | capability | stage | type | importance` — meaningful retrieval observability instead of opaque final scores.

**The architectural transition:** The system is evolving from vector similarity retrieval to a **retrieval policy engine**. Retrieval ranking is no longer just "which embedding is closest" — it is "which chunk is most operationally relevant given the current lifecycle context."

**Expected effects (without touching prompts):**
- Better cancellation reasoning, less transport leakage
- More operational chunks selected, more stable lifecycle retrieval
- Cleaner evidence generation, better eval performance

**Important — do NOT over-tune scores yet:** The exact numbers (0.20, 0.30, -0.35) are not sacred. The goal right now is retrieval semantics infrastructure, not perfect ranking. Tuning comes later using evals.

**Next step:** Step 4.5 — Retrieval Observability & Diagnostics. Log retrieval decisions, explain why chunks ranked, trace suppression, debug lifecycle mismatches, inspect retrieval failures systematically. That is where real production LLMOps visibility starts.

---

## Step 4.3: Structured retrieval filtering engine + retrieval pipeline extraction

**Category:** Metadata-Driven Retrieval Architecture

**What:** Replaced all legacy topic-string-based retrieval filtering with structured metadata-driven filtering. Extracted retrieval orchestration out of `rag_pipeline.py` into a dedicated retrieval layer. This is where retrieval stops depending on topic naming conventions and starts depending on structured operational semantics.

**The problem — internal architectural inconsistency:**

After Steps 4.1 and 4.2, the system had structured metadata on chunks but the actual retrieval engine was still behaving like legacy topic-string retrieval. Code like `chunk_topic.startswith(domain)` or `if domain in topic` was still the filtering mechanism. That is fragile and fundamentally non-scalable — naming drift breaks retrieval, taxonomy changes break retrieval, and lifecycle filtering remains implicit. This mismatch is exactly what caused the earlier "No relevant context found" failures.

**What was built — three new files, one major refactor:**

1. **`app/core/rag/retrieval_metadata.py`** — Metadata access abstraction layer. Helper functions (`get_capability()`, `get_lifecycle_stage()`, `get_knowledge_type()`, `get_visibility()`, etc.) that create a metadata abstraction boundary. Production systems never scatter `chunk["metadata"]["capability"]` everywhere — that creates schema coupling, migration pain, and retrieval fragility. This seems small but enables future schema evolution without touching retrieval logic.

2. **`app/core/rag/retrieval_filtering.py`** — Canonical retrieval semantics layer. `apply_structured_filters()` replaces ALL legacy topic-prefix filtering with:
   - **Visibility enforcement:** `internal_only` chunks never pass through
   - **Hard capability filtering:** `capability not in step_domains` → excluded. `capability` is now the primary retrieval scope, not topic names
   - **Lifecycle-aware boosting:** chunks whose `lifecycle_stage` matches `step.rag_topic` get a +0.35 score boost
   - **Transport suppression:** `transport_behavior` knowledge type gets a -0.25 penalty
   - **Retrieval observability:** debug output now prints `adjusted_score | capability | stage | type` — debugging reflects retrieval semantics instead of raw topic strings

3. **`app/core/rag/retrieval_pipeline.py`** — Retrieval orchestration layer. `build_retrieval_context()` centralizes the entire retrieval grounding pipeline that was previously scattered inside `ask_with_context()`:
   - Vector retrieval → structured filtering → noise suppression → fallback → LLM chunk selection → lifecycle extraction → distillation → operational evidence
   - Returns a structured result: `filtered_chunks`, `distilled_chunks`, `lifecycle_facts`, `operational_evidence`

4. **`app/core/llm/rag_pipeline.py`** — Refactored to delegate retrieval orchestration. The massive retrieval block inside `ask_with_context()` was replaced with a single call to `build_retrieval_context(query, step)`. `rag_pipeline.py` becomes orchestration-only: retrieve → build context → build prompt → generate → sanitize.

**Key architectural shifts:**

| Before | After |
|--------|-------|
| Topic naming = retrieval logic | Metadata semantics = retrieval logic |
| Pipeline-centric retrieval (everything in `rag_pipeline.py`) | Retrieval-layer-centric (dedicated modules) |
| `chunk_topic.startswith(domain)` | `capability not in step_domains` |
| Debug output shows raw topics | Debug output shows capability / stage / type |
| 5 responsibilities in one file | Separated: filtering, metadata, orchestration, pipeline |

**Important design decision — `capability` replaces `domain` as primary retrieval scope:**

Previously `payment_status` was used as a domain (conflating capability and lifecycle stage). Now the system separates `capability` (workflow/API area) from `lifecycle_stage` (operational phase). This distinction was the root cause of retrieval failures in Step 3.7.

**Responsibility boundaries after this step:**

| Layer | File | Responsibility |
|-------|------|----------------|
| Metadata access | `retrieval_metadata.py` | Schema abstraction |
| Retrieval filtering | `retrieval_filtering.py` | Metadata semantics, suppression, boosting |
| Retrieval orchestration | `retrieval_pipeline.py` | Retrieval grounding pipeline |
| Lifecycle grounding | `lifecycle_facts.py` | Operational state extraction |
| Operational abstraction | `operational_distiller.py` | Noise removal |
| Explicit grounding | `operational_evidence.py` | Evidence statements |
| Generation constraints | `prompt.py` | Prompt assembly |
| High-level orchestration | `rag_pipeline.py` | Retrieve → prompt → generate → sanitize |

**Expected effects:**
- Cleaner retrieval, less transport leakage, more lifecycle-focused chunks
- More stable retrieval, better eval behavior, easier debugging
- Initial retrieval regressions expected — structured semantics now expose metadata problems that semantic similarity previously masked. That is good.

**What NOT to do yet:** Reranking, graph retrieval, hybrid BM25, multi-agent orchestration. Retrieval semantics are still stabilizing.

**Note on temporary import coupling:** `retrieval_pipeline.py` currently imports `is_noise_chunk` and `extract_lifecycle_facts` from `rag_pipeline.py`. This is temporarily ugly but acceptable — these will be extracted into dedicated modules later. Do NOT over-refactor immediately.

**Next step:** Step 4.4 — Lifecycle-Aware Retrieval Scoring. Lifecycle stages get weighted more intelligently, operational states influence ranking, cancellation/failure chronology becomes retrieval-aware. Retrieval starts behaving like **operational reasoning retrieval** instead of semantic document search.

---

low, payload, schema, rules, explanation |
| `mechanism` | What transport mechanism? | webhook, socket, polling, http |
| `visibility` | Who should see this? | public_integrator, internal_only |
| `importance` | How should retrieval weight this? | low, medium, high, critical |

**Design principle:** Each metadata field answers ONE semantic question only. The current system violates this heavily — e.g., `"type": "flow"` is ambiguous (lifecycle? structure? operational behavior? chronology?). That ambiguity destroys scalable retrieval.

**Why current flow domains are too generic:** `"domain": ["payment"]` is almost useless architecturally because "payment" contains validation, completion, cancellation, refunds, sockets, polling, reconciliation, disputes, notifications. Hard filtering on "payment" becomes noisy immediately.

**Why current topics are too implementation-oriented:** `socket_payment_completed_payload` should NOT participate equally in general operational retrieval. Payload schema docs and operational lifecycle docs are different knowledge classes. The current vector store treats them similarly — that is dangerous for retrieval precision.

**Retrieval priority rules (documented in `docs/rag_taxonomy.md`):**

| Priority | Matching fields |
|----------|----------------|
| Highest | capability, lifecycle_stage, operational_state |
| Medium | business_domain, knowledge_type |
| Lower | artifact_type, mechanism |

Suppression rules: `transport_behavior` and `payload` chunks suppressed unless explicitly requested or operational evidence is insufficient. `internal_only` chunks must never reach generation.

**Key insight for this system:** Lifecycle stage is more important than semantic similarity. "Why was payment cancelled?" should prioritize cancellation lifecycle chunks even if webhook cancellation payload chunks are more semantically similar. Lifecycle relevance > embedding similarity.

**Implementation artifacts:**
- `docs/rag_taxonomy.md` — canonical taxonomy definition with retrieval priority rules
- `app/core/rag/chunk_schema.py` — Pydantic models: `ChunkMetadata` (9 structured fields) + `RAGChunk` (id, metadata, tags, content)

**What this step did NOT change:**
- No retrieval logic changes, no embedding changes, no prompt changes
- No chunk migration yet — taxonomy must be locked before migration begins
- Taxonomy mistakes become extremely expensive later, so the schema was defined separately before any data transformation

**The real transition:** The system is evolving from semantic chunk retrieval to **knowledge-governed retrieval**. That is enterprise-grade architecture. Once systems become domain-aware, flow-aware, and lifecycle-aware, you stop having "just embeddings" and start having **knowledge taxonomy engineering**.

**Result:** Explicit retrieval contracts now exist. Everything downstream (retrieval, filtering, reranking, suppression, observability, evals) can depend on structured metadata fields instead of topic string conventions.

**Next step:** Step 4.2 — Chunk Metadata Migration. Transform existing chunks into canonical `RAGChunk` objects using the new schema. Keep v1 and v2 side-by-side. Do not overwrite legacy data.
