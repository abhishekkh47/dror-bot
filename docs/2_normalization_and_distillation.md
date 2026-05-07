# Phase 3 — Structured Fact Extraction

Continues from `rag_evolution.md` (Phases 1-2: Retrieval Stability + Lifecycle Grounding).

The system is transitioning from **advanced retrieval** to **state-grounded reasoning engine**. This phase moves reasoning BEFORE generation instead of INSIDE generation.

---

## Step 3.1: Canonical lifecycle fact model (current, uncommitted)

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
