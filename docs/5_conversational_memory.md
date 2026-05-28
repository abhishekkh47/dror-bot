# Phase 6 — Conversational Memory & Investigation Continuity

Continues from `4_execution_evaluation.md` (Phase 5: Execution Evaluation & Reliability).

Phase 5 delivered comprehensive execution evaluation, adaptive retrieval with retry telemetry, stability/coherence/conflict/ambiguity analysis, evidence attribution, reasoning separation, and reliability-aware response governance. Retrieval intelligence is no longer the bottleneck.

**The new bottleneck:** Retrieval still treats every query as independent. The system stores operational memory (prior lifecycle facts, discussed topics, investigation history) but retrieval does not USE that memory. Multi-turn support conversations drift, troubleshooting loses continuity, and retrieval becomes inconsistent across turns.

**Key principle:** Operational memory is useless unless retrieval behavior adapts to it. Enterprise support systems require **state-aware retrieval**, not merely memory storage.

---

## Step 5.1: Memory-aware retrieval prioritization

**Category:** State-Aware Retrieval Orchestration

**What:** Introduced memory-aware retrieval boosting that adapts retrieval ranking based on ongoing investigation context — previously discussed topics, prior operational conclusions, and troubleshooting history. Retrieval now prioritizes evidence that continues the current investigation instead of treating each query as a fresh, unbiased search.

**The problem — stateless retrieval in a stateful system:**

Example flow:
1. User: "payment failed after processing" → system retrieves processing failure evidence
2. User: "it was cancelled afterward" → memory stores `processing_started`, `processing_failed`, `cancellation`

But retrieval still does fresh unbiased search for query 2 — potentially retrieving auth chunks, webhook chunks, or unrelated lifecycle states instead of continuing the processing → cancellation investigation. That breaks conversational continuity and makes troubleshooting feel stateless.

**What was built:**

**`app/core/memory/memory_retrieval.py`** — `apply_memory_retrieval_boost(retrieved_chunks, session_memory)`:

Two boosting signals:

| Signal | Boost | What it does |
|--------|-------|-------------|
| Topic continuity | +0.20 | Chunks matching previously discussed topics rank higher |
| Lifecycle continuity | +0.15 | Chunks containing lifecycle keywords from operational history (processing, cancellation) rank higher |

Reads from `session_memory.discussed_topics` and `session_memory.operational_history`. Re-sorts chunks by adjusted score after boosting.

**Key design decisions:**
- **Deterministic metadata-aware boosting** — NOT query rewriting with LLMs, NOT autonomous planners, NOT agent loops
- **Additive boost, not override** — memory guides retrieval continuity but does NOT override fresh evidence. Prior topics get a bonus, not exclusive access
- **Applied before filtering** — memory boost runs on raw vector search results, then structured filtering/selection proceeds normally on the boosted ranking

**Pipeline integration:**
- `retrieval_pipeline.py` — `build_retrieval_context()` now accepts optional `session_memory` parameter. After `store.search()`, applies memory boost if memory is provided
- `rag_pipeline.py` — `ask_with_context()` now accepts optional `session_memory` parameter, passes through to `build_retrieval_context()`

**What this changes:**

| Before | After |
|--------|-------|
| Every query retrieves independently | Retrieval adapts to investigation context |
| Prior turns forgotten by retrieval | Previously discussed topics boost relevant chunks |
| Troubleshooting drifts across turns | Lifecycle continuity maintained |
| Conversations feel stateless | Conversations feel continuous |

**Important — do NOT over-boost prior topics:**
- Memory should guide retrieval continuity, NOT override fresh evidence
- Do NOT trap retrieval into narrow loops or permanently bias investigations
- Prior context is a ranking signal, not a filter

**What this step did NOT change:**
- No retrieval logic changes beyond score boosting — filtering, selection, validation all unchanged
- Memory structure (`session_memory`) is assumed to exist — session management itself is not implemented here
- Boost weights (0.20, 0.15) are approximate — tuning comes from eval data

**Next step:** Step 5.2 — Full memory orchestration integration. Memory modules exist but are disconnected from the pipeline lifecycle — orchestration must own memory load/save/reset/update internally.

---

## Step 5.2: Memory orchestration integration — closing the 6 critical gaps

**Category:** Orchestration Lifecycle Coherence

**What:** Integrated the entire memory subsystem into the orchestration lifecycle. Memory modules (store, updater, summarizer, reset, retrieval boost) existed as isolated components — this step wired them into a coherent investigation lifecycle managed internally by `ask_with_context()`. Six critical integration issues were identified and resolved.

**The root problem — partial integrations, disconnected intelligence modules:**

The architecture had strong individual memory components but **incomplete orchestration integration**. The weakness was not missing sophistication — it was missing lifecycle wiring. Memory existed but was dead code, disconnected from the pipeline's actual execution flow.

### Critical Issue #1: Session memory externally injected instead of lifecycle-managed

**Before:** `ask_with_context(query, step, session_memory=None)` — caller must manage memory lifecycle (load, save, reset). Orchestration layer does not own investigation lifecycle, creating inconsistent state management and session bugs.

**After:** `ask_with_context(query, step, session_id="default")` — orchestration owns the full memory lifecycle internally:
```python
session_memory = get_session_memory(session_id)
if session_memory and should_reset_investigation(session_memory, query):
    session_memory = reset_session_memory(session_id)
if not session_memory:
    session_memory = SessionMemory(session_id=session_id)
```

### Critical Issue #2: Memory never updated

**Before:** `update_session_memory()` and `save_session_memory()` existed but were never called anywhere in `rag_pipeline.py`. Memory system did absolutely nothing operationally.

**After:** After response generation, memory is updated and saved:
```python
session_memory = update_session_memory(
    session_memory=session_memory,
    lifecycle_facts=lifecycle_facts,
    reasoning_breakdown=reasoning_breakdown,
    evidence_attribution=evidence_attribution,
    response=response,
)
save_session_memory(session_memory)
```

### Critical Issue #3: Memory summarizer never used

**Before:** `summarize_investigation_state()` existed but was never called. Memory compression did not exist operationally.

**After:** `update_session_memory()` now calls `summarize_investigation_state()` at the end, populating `session_memory.investigation_summary` with `active_lifecycle_states`, `major_operational_findings`, and `active_topics`.

**SessionMemory model also updated** with `investigation_summary: Dict = {}` field.

### Critical Issue #4: Memory retrieval boosting too aggressive

**Before:** Topic continuity boost +0.20, lifecycle continuity boost +0.15 — unbounded cumulative continuity bias that could cause old operational topics to dominate future retrieval in long investigations.

**After:** Boost values reduced to prevent retrieval drift. Memory should guide continuity, not permanently bias investigations.

### Critical Issue #5: Investigation reset logic using unreliable string overlap

**Before:** `should_reset_investigation()` checked `topic in query_lower` against `previous_topics` — but `previous_topics` contains metadata taxonomy topics (e.g., `platform_transaction`), not natural-language query concepts. This created false resets.

**After:** Unreliable string overlap check commented out. Reset now only triggers on explicit reset-topic detection (`RESET_TOPICS = ["authentication", "headers", "intent_creation"]`). Semantic investigation segmentation deferred to a future step.

### Critical Issue #6: Memory context missing from prompt integration

**Before:** Memory existed and retrieval used it for boosting, but the prompt itself had zero visibility into investigation history. Memory had no influence on generation.

**After:** Memory context injected into prompt via `build_prompt_with_step()`:
```python
memory_context = (
    f"Lifecycle States: {memory_summary.get('active_lifecycle_states', [])}\n"
    f"Operational Findings: {memory_summary.get('major_operational_findings', [])}\n"
    f"Active Topics: {memory_summary.get('active_topics', [])}"
)
```

Prompt template updated with `PREVIOUS_INVESTIGATION_CONTEXT: {memory_context}` section placed before `ANSWER`.

**Implementation artifacts — full memory module inventory:**

| File | Responsibility |
|------|---------------|
| `app/core/memory/session_memory.py` | `SessionMemory` Pydantic model |
| `app/core/memory/memory_store.py` | In-memory session storage (`get`, `save`) |
| `app/core/memory/memory_updater.py` | Update memory with lifecycle facts, reasoning, evidence, response |
| `app/core/memory/memory_summarizer.py` | Compress investigation state into summary |
| `app/core/memory/memory_reset.py` | Investigation reset detection + execution |
| `app/core/memory/memory_retrieval.py` | Memory-aware retrieval score boosting |

**The architectural transition:**

| Before | After |
|--------|-------|
| Memory modules existed as isolated files | Memory integrated into orchestration lifecycle |
| `ask_with_context()` was stateless orchestration | `ask_with_context()` owns investigation lifecycle |
| Memory never updated, never summarized | Memory updated and summarized after every turn |
| Prompt had zero memory visibility | Prompt receives investigation context |
| Investigation reset was unreliable | Reset limited to explicit topic shifts (safe) |

**Key insight:** The system's weakness was not missing sophistication — it was **incomplete orchestration integration**. Disconnected intelligence modules are worse than missing modules because they create false confidence that a capability exists.

**What this step did NOT change:**
- Memory store is in-memory (`dict`) — not persisted across server restarts
- Memory boosting weights still need eval-driven tuning
- Investigation segmentation is primitive (explicit topic list) — semantic segmentation comes later
- Memory context in prompt is formatted but not yet structured with evidence IDs

**Next step:** Step 5.3 — Investigation State Summarization refinement and long-session continuity management. Operational memory continuously grows — state compression, memory distillation, and scalable memory orchestration become the next production scaling frontier.
