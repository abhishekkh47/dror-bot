# Phase 3 — Structured Fact Extraction

Continues from `rag_evolution.md` (Phases 1-2: Retrieval Stability + Lifecycle Grounding).

The system is transitioning from **advanced retrieval** to **state-grounded reasoning engine**. This phase moves reasoning BEFORE generation instead of INSIDE generation.

---

## Step 3.6: Minimal controlled generation — evidence-driven prompts

**What:** Refactored the giant monolithic prompt into structured, separated sections (`SYSTEM_RULES`, `LIFECYCLE_RULES`, `RESPONSE_RULES`, `PROMPT_TEMPLATE`). Removed duplicated lifecycle reasoning rules that are now enforced structurally by `LifecycleFacts`, contradiction resolution, and operational evidence. The prompt's role shifted from validator/reasoner/suppressor to **evidence interpreter**.

**Key architectural shift:**
- Before: `Prompt → tries to enforce truth`
- After: `Architecture → establishes truth, Prompt → renders truth`

The prompt no longer performs lifecycle reasoning, chronology reconstruction, or contradiction suppression. Those are now handled by dedicated layers. The prompt only defines behavior policy.

**The trap this step avoids:** Most people aggressively delete prompt rules after building architectural grounding, thinking "the architecture handles it now." That causes regressions because evidence extraction is still imperfect, retrieval still occasionally leaks noise, and operational nuance still exists in raw chunks. This step is **prompt simplification**, NOT prompt elimination.

**Key changes:**

`prompt.py` — refactored into separated sections:
- `SYSTEM_RULES` — role definition, evidence-only constraint, no speculation, no internal leakage
- `LIFECYCLE_RULES` — processing requires creation, cancellation implies failure, never describe post-processing failure as creation failure, terminal state consistency
- `RESPONSE_RULES` — concise operational answers, no infra details unless asked, state insufficient evidence when needed
- `PROMPT_TEMPLATE` — clean assembly: system rules → lifecycle rules → response rules → operational evidence → supporting context → query → answer

**Responsibility hierarchy after this step:**

| Layer | Responsibility |
|-------|---------------|
| Retrieval | Relevant evidence |
| LifecycleFacts | Operational state |
| ContradictionResolver | Lifecycle consistency |
| OperationalEvidence | Grounded truth |
| Prompt | Concise rendering constraints |
| Sanitizer | Final cleanup safety net |

**What was removed from prompts:**
- Duplicated lifecycle rules like "never say intent creation failed after processing" — now enforced by contradiction resolution + operational evidence
- Chronology reconstruction guidance — now handled by `infer_derived_state()`
- Contradiction warnings — now handled by `resolve_contradictions()`
- Wording patches — now handled by operational distiller

**What was kept:**
- Anti-speculation rules (policy constraint)
- No-internal-leakage rules (policy constraint)
- Concise-response rules (policy constraint)

These are **behavior policy**, not lifecycle reasoning. Important distinction — prompts should define behavior policy, NOT operational truth inference.

**Why structured sections matter:** Mixed prompts are hard to debug, hard to version, hard to evaluate, and prone to instruction conflicts. Separated sections enable: easier debugging (which section caused the regression?), easier governance (version each section independently), easier evaluation (test policy rules vs lifecycle rules separately), lower instruction collision risk.

**Expected effects (without adding more prompt complexity):**
- More stable outputs, fewer contradictory sentences
- Less over-explanation, shorter responses
- Less hallucinated chronology, more deterministic behavior
- Signal that architecture is replacing prompting

**What this step did NOT change:**
- Did not remove sanitizer — stays as final safety net
- No reranking, graph reasoning, multi-agent decomposition, model routing, or fine-tuning
- Current bottleneck is evidence quality and evaluation, not retrieval sophistication

**Result:** The system now resembles enterprise support AI infrastructure instead of giant-prompt RAG. This aligns with the "Prompt Governance & Versioning" and "Enterprise RAG Pipeline" progression.

**Next step:** Step 3.7 — Evaluation & Regression Framework. Once architecture becomes layered, deterministic regression detection becomes critical. Evals matter more than prompts at this stage — one of the clearest markers of moving from prototype GenAI into production-grade AI engineering.

**Current flow**
Retrieval
→ Chunk Selection
→ Lifecycle Extraction
→ Contradiction Resolution
→ Operational Distillation
→ Operational Evidence
→ Prompt Assembly
→ Generation
→ Sanitization

---

## Step 3.5: Distilled operational evidence layer
**What:** Introduced a structured evidence builder that converts normalized `LifecycleFacts` into explicit operational truth statements. These statements are prepended to the context as `OPERATIONAL_EVIDENCE`, with raw chunk text demoted to `SUPPORTING_CONTEXT`. The LLM now receives a dual-context grounding hierarchy: evidence first, chunks second.
**Why this is the most important transition so far:** Up to now, the generator was still fundamentally operating on paragraph-oriented text — even if cleaner after distillation. The model still parsed paragraphs, reconstructed meaning, prioritized signals, inferred causality, and decided what matters. Too much implicit reasoning inside generation. After this step, the LLM is no longer *interpreting chunks* — it is *rendering grounded evidence*. The system stops behaving like "RAG + prompt engineering" and starts behaving like a **state-grounded reasoning pipeline**.
**Key changes:**
New file `operational_evidence.py`:
- `build_operational_evidence(facts: LifecycleFacts)` — converts each lifecycle fact into a plain operational statement: `intent_created=True` → "payment intent creation succeeded", `auto_completion_failed=True` → "auto-completion failed during processing", `final_state="cancelled"` → "final transaction state is cancelled"
`rag_pipeline.py`:
- After `extract_lifecycle_facts()` and `resolve_contradictions()`, calls `build_operational_evidence(lifecycle_facts)`
- Context assembly now builds dual-context:
  ```
  OPERATIONAL_EVIDENCE:
  - payment intent creation succeeded
  - processing started
  - auto-completion failed
  - transaction cancelled after processing failure
  SUPPORTING_CONTEXT:
  <distilled chunk text>
  ```
- Evidence becomes primary grounding, raw chunks become secondary (for nuance only)
**Before vs after — what the LLM sees:**
Before:

---

## Step 3.4: Operational distillation layer (current, uncommitted)

**What:** Added a deterministic pre-generation context shaping layer that transforms raw implementation-heavy chunks into clean operational evidence. This is the "context compression" step originally planned — but done correctly now that lifecycle facts, inference, and contradiction resolution are in place. Without those foundations, this would have been naive summarization that destroys lifecycle correctness.

**What this is NOT:** Text compression, LLM summarization, or chunk shortening. Summarization collapses lifecycle boundaries, invents causality, and destroys chronology. This is **operational abstraction** — preserving lifecycle meaning while removing implementation mechanics.

**The problem this solves:** Even with chunk selection, noise penalties, prompts, and sanitization, the generator still received raw chunks containing socket mechanics, webhook ordering, audit logging, DB transaction behavior, room joins, retry semantics. The model sees ~80% implementation noise and starts leaking internals, over-explaining, and hallucinating causal chains.

**Key changes:**

New file `operational_distiller.py`:
- `NOISE_PATTERNS` — regex patterns for implementation noise: socket internals, webhook/callback details, audit/logging, DB transaction/wallet lock mechanics, push notifications, WhatsApp
- `clean_operational_text(text)` — removes lines matching noise patterns while preserving lifecycle-relevant lines. Deterministic, no LLM involved
- `distill_chunks(filtered_chunks)` — applies `clean_operational_text` to each chunk, returns cleaned chunks with topic/tags preserved

`rag_pipeline.py`:
- Inserted `distill_chunks(filtered)` between chunk selection and context assembly
- Context builder now loops over distilled chunks instead of raw filtered chunks
- Added lifecycle-safe wording replacements in context normalization (e.g. "payment intent creation failed" → "payment processing failed after intent creation") — applied to distilled content before prompt assembly

**Pipeline becomes:**
```
Retrieval → Chunk Selection → Lifecycle Extraction → Contradiction Resolution → Operational Distillation → Prompt Assembly → Generation
```

Previously: `raw retrieval → prompt`. Now: `retrieval → operational abstraction → prompt`.

**Why deterministic, not LLM-based:** Summarization destroys chronology, invents causality, and collapses lifecycle stages. Deterministic regex filtering is conservative but safe. Only later, once behavior is observed, can abstraction models be safely added.

**Design rule — what to keep vs remove:**

| Keep | Remove |
|------|--------|
| Processing failed | Socket events |
| Transaction cancelled | Webhook ordering |
| Auto-completion failed | Room joins |
| Lifecycle chronology | Retry semantics |
| Causal transitions | DB locks / wallet locks |
| Failure semantics | Audit logging |
| | Push notifications / WhatsApp |

Unless the user explicitly asks about those implementation details.

**Important:** This first version is intentionally conservative — only removes obvious implementation noise. Over-filtering can accidentally strip lifecycle chronology, causal transitions, or failure semantics. Behavior needs to be observed before aggressive stripping.

**Expected effects (without changing prompts):**
- Shorter answers
- Less infra leakage
- Less webhook/socket discussion
- More lifecycle-focused answers
- Cleaner operational phrasing

**What this step did NOT change:**
- Did not remove prompt constraints or sanitizers — safety redundancy stays
- Did not add LLM summarization or abstraction models
- Noise patterns are conservative, not aggressive

**Result:** First pre-generation context shaping layer. The generator now receives operationally-cleaned evidence instead of raw implementation-heavy chunks.

**Next step:** Step 3.5 — Distilled Operational Fact Generation. Prompt size shrinks dramatically, raw chunk text becomes secondary, generation relies primarily on lifecycle facts + distilled operational evidence. The system begins behaving like a grounded reasoning engine instead of a constrained summarizer.

---

## Step 3.3: Contradiction resolution engine

**What:** Split `infer_derived_state()` into two separate responsibilities: inference (deriving implied facts) and contradiction resolution (enforcing operational consistency). Added `resolve_contradictions()` method to `LifecycleFacts` that prevents impossible lifecycle states BEFORE generation. Pipeline now runs: raw extraction → inferred relationships → contradiction normalization.

**Key architectural shift:** Before this step, contradictions were handled by prompts ("never say intent creation failed") and sanitizers (regex rewriting). That's too late — the generator could still receive invalid state. After this step, the system makes contradictory states impossible before the prompt even exists. The generator NEVER receives invalid state.

**Examples of contradictions this prevents:**

| Contradiction | Why impossible | Resolution |
|---------------|---------------|------------|
| `processing_started=True` + `intent_created=False` | Processing cannot start before creation | Force `intent_created=True` |
| `processing_completed=True` + `transaction_cancelled=True` | Completed transactions cannot be cancelled | Force `transaction_cancelled=False` |
| `processing_completed=True` + `processing_failed=True` | Conflicting terminal states | Completion wins — force `processing_failed=False` |
| `auto_completion_failed=True` + `processing_started=False` | Impossible lifecycle ordering | Force `processing_started=True` |
| `failure_stage="intent_creation"` + `processing_started=True` | If processing started, creation succeeded | Force `failure_stage="processing"` |

**Design decision — completion wins:** `processing_completed` has highest precedence in terminal state resolution. Completion is terminal truth. This is intentional deterministic precedence — without it, state becomes ambiguous.

**Key changes:**

`lifecycle_facts.py`:
- `resolve_contradictions()` added — enforces operational consistency: processing implies creation, completion clears failure/cancellation flags, cancelled+failed resolves to "cancelled", contradictory terminal combinations are cleaned
- `infer_derived_state()` cleaned — now only infers implied relationships, no longer performs contradiction repair. Inference and normalization are separate responsibilities

`rag_pipeline.py`:
- `extract_lifecycle_facts()` now calls both in sequence: `facts.infer_derived_state()` then `facts.resolve_contradictions()`. Order matters — normalization must operate on fully inferred state, not incomplete state

**Why separation matters:** Inference (`infer_derived_state`) answers: "what else must be true given these facts?" Contradiction resolution (`resolve_contradictions`) answers: "which facts are impossible together and how do we resolve them?" Combining these creates hidden coupling. Separating them makes each independently testable and debuggable.

**What this step begins:** Formalizing operational state machine semantics. This is the real core of enterprise reasoning systems — not embeddings, not prompts. State semantics.

**What this step did NOT change:**
- Did not remove prompt constraints or sanitizers — safety redundancy stays during transition
- No compression, no summarization, no event graphing, no prompt simplification

**Result:** Before: prompt tries to avoid contradictions. After: system prevents contradictory state before prompt exists. Major production-grade transition.

**Next step:** Step 3.4 — Operational Distillation Layer. Transform raw implementation-heavy chunks into clean operational evidence before generation. NOT text compression — transforming operational evidence into grounded abstractions.

---

## Step 3.2: Fact extraction engine + deterministic lifecycle inference

**What:** Evolved `LifecycleFacts` from a passive data container into a deterministic lifecycle inference layer. Added `infer_derived_state()` method that applies normalization rules before generation. Renamed `build_failure_summary()` to `extract_lifecycle_facts()` to reflect the shift from vague summarization to deterministic state extraction. Added auto-completion failure detection and completion indicators.

**Key architectural shift:** Until now, the LLM performed lifecycle inference, chronology inference, and operational interpretation inside generation. After this step, the system infers lifecycle relationships BEFORE generation. The prompt receives already-resolved lifecycle state instead of raw ambiguity.

**Key changes:**

`lifecycle_facts.py` — added `infer_derived_state()`:
- `processing_started` ⇒ `intent_created = True` (processing implies creation succeeded)
- `auto_completion_failed` ⇒ `processing_started = True`, `processing_failed = True`, `failure_stage = "auto_completion"`
- `processing_failed + transaction_cancelled` ⇒ `final_state = "cancelled"`
- `processing_completed` ⇒ `final_state = "completed"`
- `processing_failed` (without other resolution) ⇒ `final_state = "failed"`

`rag_pipeline.py`:
- `build_failure_summary()` renamed to `extract_lifecycle_facts()` — naming reflects deterministic extraction, not vague summarization
- Added auto-completion failure detection phrases ("auto-completion fails", "auto-completion failed", "completion failure")
- Added completion detection phrases ("marked platform transaction as completed", "payment completed successfully")
- Calls `facts.infer_derived_state()` after keyword extraction — first centralized lifecycle normalization point

**Why `infer_derived_state()` is the most important change:** This is the system's first deterministic normalization layer. Previously, normalization was scattered across prompts, sanitizers, and implicit generation behavior. Now lifecycle truth starts becoming explicit architecture. Example: if `auto_completion_failed = True`, the system deterministically sets `processing_started = True` and `intent_created = True` — the LLM no longer needs to infer that chain.

**Design rule:** Extract operational truth, NOT surface wording. `"HTTP 400 returned after auto-completion failure"` → `processing_failed = True, auto_completion_failed = True`. NOT `http_400 = True`. The HTTP code is implementation detail. The lifecycle meaning is what matters.

**What this step did NOT change:**
- Did not remove prompt rules, simplify prompts, or remove sanitizers — safety redundancy stays while architecture transitions
- No contradiction engine, no distillation, no event graphs
- Still foundational — keyword extraction is primitive, but the inference layer on top is the real value

**Result:** Lifecycle truth is slowly moving OUT of natural language generation and INTO deterministic state modeling. That is how production-grade operational AI systems evolve — not through bigger prompts.

**Next step:** Step 3.3 — Contradiction Resolution. Add `resolve_lifecycle_conflicts(facts)` to catch impossible states (e.g. `intent_created = False` + `processing_started = True`) before prompt assembly.

---

## Step 3.1: Canonical lifecycle fact model

**What:** Introduced `LifecycleFacts` dataclass as the canonical lifecycle state object. Replaced the loose `failure_summary = { ... }` dict in `rag_pipeline.py` with a typed, schema-guaranteed data structure. Updated `build_failure_summary()` to return `LifecycleFacts` and updated `prompt.py` to use attribute access instead of dict keys.

**Why this step:** The dict-based lifecycle state had no schema guarantees, inconsistent fields, typo risks, and made future normalization/contradiction rules impossible. A dataclass provides a canonical reasoning interface that all downstream layers (contradiction resolution, distillation, generation) can depend on.

**Key changes:**
- New file `lifecycle_facts.py` — `LifecycleFacts` dataclass with fields: `intent_created`, `processing_started`, `processing_failed`, `processing_completed`, `transaction_cancelled`, `auto_completion_failed`, `user_cancelled`, `failure_stage`, `final_state`
- `rag_pipeline.py` — `build_failure_summary()` returns `LifecycleFacts()` instead of dict, assignments use `summary.intent_created = True`
- `prompt.py` — dict key access (`failure_summary["intent_created"]`) replaced with attribute access (`failure_summary.intent_created`)

**Design rule:** This object represents **operational lifecycle truth**, NOT implementation internals. `processing_failed = True` is operational. `socket_event_emitted = True` is infrastructure. Fields like `webhook_sent`, `db_rollback`, `notification_sent` were intentionally excluded.

**What this step did NOT change:**
- No normalization rules, no inference rules, no extraction engine, no contradiction logic
- No behavioral changes, no retrieval changes, no prompt simplification
- Foundational architecture work only — layer-by-layer so regressions are traceable

**Result:** Pipeline becomes `retrieval → chunk selection → LifecycleFacts grounding → prompt assembly → generation` instead of `retrieval → loosely structured dicts → prompt`. First transition toward deterministic grounding.

**Next step:** Step 3.2 — Fact Extraction Engine. Evolve the current primitive `build_failure_summary()` (keyword-based, boolean flags, shallow extraction) into a real extraction subsystem.
