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

**Next step:** Step 5.2 — Investigation State Summarization. Operational memory continuously grows, but there is still no state compression, investigation summarization, memory distillation, or long-session continuity management. That becomes the next major production scaling frontier: scalable operational memory orchestration.
