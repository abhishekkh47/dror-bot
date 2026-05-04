# RAG Pipeline Evolution

Tracks how the RAG pipeline evolved — what each approach did, what broke, and why we moved on.

---

## Approach 3: Step-scoped retrieval with strict topic equality

**What:** Instead of blindly returning top-k results, retrieval was scoped to the current flow step. Each step in `payment_execution.json` has a `rag_topic` field. After embedding search returned candidates, they were filtered by `chunk.topic == step.rag_topic`. If no chunks matched, the system returned an explicit out-of-scope message instead of hallucinating.

**Key changes:**
- `ask_with_context()` in `rag_pipeline.py` — does search, strict topic filter, out-of-scope boundary, then builds prompt
- `build_prompt_with_step()` in `prompt.py` — injects step title and description into the LLM prompt
- `rag_topic` added to every step in `payment_execution.json`
- `retriever.retrieve_context()` kept but no longer used by the main path (replaced by inline logic in `ask_with_context` for clarity)

**Why this over Approach 2:** Approach 2 had no concept of "where the user is in the flow." Asking "what headers are required?" returned the same API-level answer whether the user was on `create_intent` or `evaluate_status`. The retriever couldn't distinguish context. Also, `retrieve_context()` was doing too much implicitly (search + filter + fallback) making it hard to reason about.

**Result:** Questions irrelevant to the current step got a clear boundary response instead of a confused answer.

**What broke:** The filter was too strict — `rag_topic` values in the flow JSON (e.g. `create_intent_response_handling`) never matched chunk `topic` values (e.g. `create_intent_api`) because they used different naming. All 3 test cases returned "This question is not relevant" even for valid questions on the correct step.

---

## Approach 2: Embedding-based retrieval with boosted scoring
**Date:** 2026-04-29
**Commit:** `9d7ad24`

**What:** Built a proper RAG pipeline: chunks are embedded at load time using `nomic-embed-text` via Ollama, stored in an in-memory `VectorStore`. Queries are embedded at runtime, cosine similarity finds top-k candidates, and the matched context is injected into a prompt sent to `gemma:2b` via Ollama.

**Key components:**
- `embedding.py` — calls Ollama `/api/embeddings` with `nomic-embed-text`
- `vector_store.py` — loads chunks from JSON, embeds each chunk (topic + type + tags + content), stores as numpy arrays, cosine similarity search with importance/type/keyword boosting
- `retriever.py` — wraps `VectorStore.search()`, formats results as context string
- `prompt.py` — `build_prompt()` with rules: only use provided context, don't invent APIs, don't mention internals
- `llm.py` — calls Ollama `/api/generate` with `gemma:2b`
- `rag_pipeline.py` — `ask()` ties it all together: retrieve → build prompt → generate

**Scoring formula:** `(cosine_similarity + keyword_bonus) * importance_boost * type_boost`
- importance_boost: high=1.2, medium=1.0, low=0.8
- type_boost: explanation=1.1, others=1.0
- keyword_bonus: +0.1 if any query word appears in chunk content

**Why this over Approach 1:** Approach 1 had no retrieval — every query sent all knowledge to the LLM. This doesn't scale beyond a handful of chunks and wastes context window. Embedding-based search retrieves only relevant chunks.

**Result:** Queries like "Is payment synchronous?" and "What happens if auto completion fails?" return focused answers from the most relevant chunks.

**Limitations:**
- No awareness of flow state — same answer regardless of which step the user is on
- `retrieve_context()` silently falls back to unfiltered results when topic filter finds nothing, defeating the purpose of filtering
- All chunks loaded from a single JSON file — no multi-flow support
- In-memory only — embeddings are recomputed on every server restart

---

## Approach 1: Deterministic flow engine (no RAG)
**Date:** 2026-04-29
**Commit:** `30ffed7`

**What:** Built a state machine that walks through a predefined flow (`payment_execution.json`). Each step has a type (ACTION, DECISION, INFO). The engine advances through steps based on user input. DECISION steps branch based on the input value; other steps auto-advance. Sessions track current position and history.

**Key components:**
- `flow_loader.py` — loads flow JSON, builds step map for O(1) lookup
- `flow_engine.py` — `start_flow()`, `process_input()`, `get_current_step()`
- `session_store.py` — in-memory session management with UUID-based sessions
- `types.py` — Pydantic models for Step, Flow, Session with validation (duplicate IDs, next-reference integrity, type/option consistency)

**Result:** A working API that guides the user through the payment flow step by step. No AI, no knowledge — just deterministic state transitions.

**Limitations:**
- No ability to answer questions — the system can only advance through steps
- User gets step metadata (title, description) but no domain knowledge
- To add knowledge, you'd have to hardcode answers per step
