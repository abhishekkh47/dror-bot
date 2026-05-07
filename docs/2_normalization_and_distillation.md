# Phase 3 — Structured Fact Extraction

Continues from `rag_evolution.md` (Phases 1-2: Retrieval Stability + Lifecycle Grounding).

The system is transitioning from **advanced retrieval** to **state-grounded reasoning engine**. This phase moves reasoning BEFORE generation instead of INSIDE generation.

---

## Step 3.3: Contradiction resolution engine (current, uncommitted)

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
