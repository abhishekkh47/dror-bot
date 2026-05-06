# RAG Pipeline Evolution

Tracks how the RAG pipeline evolved — what each approach did, what broke, and why we moved on.

---

## Approach 8: From retrieval quality to answer quality

*Prompt discipline + soft intent boost + chunk selection pipeline*

**What:** Addressed the three problems exposed by Approach 7.1: LLM answer precision, hard intent filtering, and noisy chunk aggregation. Applied fixes at three layers: prompt, scoring, and post-retrieval selection.

**Key shift:** The main failure was no longer retrieval — it was answer contamination. Retrieved chunks were relevant, but the LLM blended them, mixed lifecycle stages, and hallucinated details. The bottleneck moved from "getting the right chunks" to "using them correctly."

**Changes — prompt discipline (`prompt.py`):**
- Restructured prompt with explicit sections: USER QUESTION, CURRENT STEP, CONTEXT, ANSWERING RULES, STRICT CONTEXT RULES, RESPONSE STYLE
- Added lifecycle stage awareness: "Distinguish carefully between intent creation, processing, auto-completion, cancellation, final settlement"
- Added hard constraint: if failure occurs AFTER intent creation, never say "intent creation failed" — instead say "the payment failed after intent creation"
- Webhook/socket/polling details suppressed unless explicitly asked
- Response capped at 2-4 sentences, no markdown headings, no bullet points unless requested

**Changes — soft intent boost (`vector_store.py`):**
- Replaced hard intent filter (`if intent not in chunk_tags: continue`) with soft boost/penalty:
  - Intent matches chunk tags → 1.5x boost
  - Intent doesn't match → 0.7x penalty (chunk stays in scoring, just deprioritized)
- Rebalanced scoring formula to reduce embedding dominance:
  ```
  final_score = (base_score * 0.6 + tag_component * 0.25 + intent_component * 0.15) * keyword_boost
  ```
  - `base_score` = similarity * importance * type * critical (60% weight)
  - `tag_component` = tag_boost * 2.5 weight (25% weight)
  - `intent_component` = intent_boost * 2.0 weight (15% weight)
- Tag score normalization: `1 + min(1.5, tag_score / 2)` — prevents tag explosion

**Changes — post-retrieval chunk selection (`rag_pipeline.py`):**
- Noise chunk blacklist: `is_noise_chunk()` removes known-bad chunks (`create_intent_pending_event_without_completion`) before scoring
- Aggressive top-N trimming: only top 2 chunks from the same semantic group (matching topic prefix) are sent to the LLM
- `sanitize_response()` — post-LLM guard that catches residual phase-mixing (replaces "intent creation failed" with "payment failed after intent creation", blocks answers that leak webhook/socket internals)

**Test results (3 generalization queries):**

| Case | Query | Result | Pass? |
|------|-------|--------|-------|
| 1 | "why was payment cancelled?" | Correctly describes auto-cancel after error during auto-completion | Yes |
| 2 | "payment didn't complete" | Correctly describes failure after intent creation, HTTP 400 response | Yes |
| 3 | "transaction failed after processing" | Correctly describes processing-stage failure, cancelled status in DB | Yes |

**What's still weak:**

1. **Answer contamination is reduced but not eliminated.** The LLM still occasionally blends lifecycle stages. `sanitize_response()` is a brittle band-aid — keyword-based post-processing that will miss new phrasings.

2. **Noise blacklist is manual.** `is_noise_chunk()` hardcodes specific chunk IDs. This doesn't scale — every new problematic chunk requires a code change.

3. **Chunk selection is position-based, not relevance-based.** Taking top 2 from the same topic prefix is a heuristic. The LLM receives all selected chunks equally and can blend information from a chunk that's topically related but semantically wrong for the specific question.

**Next step: LLM-based chunk selector.** The current pipeline is:
```
query → vector retrieval → top chunks → final LLM answer
```

The actual bottleneck is chunk utilization, not retrieval quality. A reranker would improve ordering precision, but the real problem is noisy chunk aggregation. A lightweight LLM-based chunk selector addresses this directly:
```
query → vector retrieval → LLM chunk selector → compressed relevant context → final answer LLM
```

This is the correct sequencing before adding a full reranker, because the system needs to learn which parts of retrieved chunks are relevant to the specific question before worrying about chunk ordering.

---

## Approach 7.1: Analysis — what semantic intent exposed

**What's working (achieved so far):**
- Domain-aware retrieval
- Semantic intent detection
- Meaningful ranking

**Retrieval debug confirms correct ranking:**
```
1.9167 | create_intent_what_happens_on_completion_failure  ← correct, rank 1
1.6688 | create_intent_auto_cancel_behavior                ← correct, rank 2
```
The wrong chunk (`pending_event_without_completion`) is gone. Only failure-relevant chunks remain. Ranking is now dominated by intent + domain, not noise.

**What was still broken (fixed in Approach 8):**

1. **LLM answer precision — semantic distortion.** The LLM returned "payment intent was not created successfully" for a query about post-processing failure. The retrieved chunks correctly describe auto-completion failure AFTER creation, but the LLM generalized it into "creation failed." Root cause: prompt allowed generalization beyond the exact lifecycle stage.

2. **Coarse intent model — failure types collapsed.** Single `failure` intent covered creation failure, auto-completion failure, and cancellation — different lifecycle stages with different answers.

3. **Hard intent filtering too aggressive.** `if intent and intent not in chunk_tags: continue` — mis-tagged or incomplete tags caused correct chunks to be silently dropped.

4. **No stage awareness.** System knew domain and intent but not lifecycle stage. Could not distinguish "why did intent creation fail?" from "why did payment fail after processing?"

---

## Approach 7: Semantic intent detection

**What:** Replaced keyword-based `detect_intent(query_tokens)` with embedding-based `detect_intent_semantic(query)`. Instead of matching against a hardcoded word list, the query is embedded and compared via cosine similarity against example phrases for each intent. This means "cancelled", "didn't complete", and "timed out" can all resolve to the `failure` intent without being in a keyword map.

**Key shift:** keyword-driven RAG → intent-aware semantic retrieval.

**Key changes:**
- `detect_intent(query_tokens)` removed — no more keyword matching
- `detect_intent_semantic(query: str)` added — embeds the query, compares against `INTENT_DEFINITIONS` examples, returns the best-matching intent if score > 0.75 threshold
- `INTENT_DEFINITIONS` added to `constants.py` — maps intents to example phrases:
  - `failure`: "payment failed", "transaction failed", "payment cancelled", "payment did not complete", "payment error", "payment unsuccessful"
  - `success`: "payment successful", "transaction completed", "payment done"
- `search()` updated: `detect_intent_semantic(query)` replaces `detect_intent(query_tokens)` — takes the raw query string instead of tokenized set
- Intent filtering unchanged: `if intent and intent not in chunk_tags: continue`

**Why this over Approach 6:** Approach 6 used keyword matching (`if t in ["fail", "fails", "failed", "failure", "error"]`). This broke on any rephrasing that didn't use those exact words — "cancelled", "didn't complete", "timed out" all missed the intent entirely. The system was overfitted to specific keywords.

**What this fixes:**

| Query | Old (keyword) | New (semantic) |
|-------|--------------|----------------|
| "why was payment cancelled?" | No intent detected | → matches "payment cancelled" → `failure` |
| "payment didn't complete" | No intent detected | → matches "payment did not complete" → `failure` |
| "transaction failed after processing" | `failure` (keyword match) | `failure` (semantic match, same result) |

**Result:** Retrieval now correctly identifies failure intent across phrasings. But exposed three deeper problems: LLM answer precision, coarse intent model, and aggressive hard filtering. See Approach 7.1 for details.

**Limitations:**
- Example phrases in `INTENT_DEFINITIONS` are still manually curated — coverage depends on anticipating user phrasings
- Every call to `detect_intent_semantic` embeds the query + all example phrases at runtime — N embedding calls per intent detection (currently 9 examples = 10 calls including query). No caching of example embeddings
- Threshold (0.75) is static — may need tuning per intent
- Only 2 intents defined (failure, success) — queries about webhooks, authentication, fees etc. have no intent and fall through to unfiltered retrieval

---

## Approach 6: Controlled retrieval architecture

**What:** Added token normalization, keyword-based intent detection, and domain filtering as pre-scoring stages inside `VectorStore.search()`. Retrieval now constrains candidates *before* scoring, instead of filtering *after*. The pipeline is now: token normalization → intent detection → domain filtering → intent filtering → semantic ranking → LLM generation.

**Why this is no longer "basic RAG":** Previous approaches scored everything and then tried to filter out bad results. Now the retrieval is constrained upfront — wrong-domain chunks are discarded before they can compete on similarity, and intent mismatches are excluded before they can be boosted by tags/keywords.

**Key changes in `vector_store.py`:**
- `normalize_token()` — maps variants to canonical forms (fails/failed/error → failure, succeeded → success)
- `detect_intent(query_tokens)` — extracts query intent from normalized tokens (e.g. "what happens if payment fails?" → intent: `failure`)
- Domain filtering: `step.domain` field determines which chunk topic prefixes are allowed. Chunks outside the domain are discarded entirely (hard cutoff, not scored)
- Intent filtering: if an intent is detected, chunks whose tags don't include that intent are skipped
- Tag scoring reworked: uses `CRITICAL_TAGS` (failure=3.0, success=2.5) and `CONTEXT_TAGS` (error_handling=1.5, webhook=1.5, etc.) from `constants.py` instead of flat weights
- Critical tag match gives an additional 1.2x similarity boost
- Keyword boost capped at 0.2 to prevent long-content bias: `1 + min(0.2, 0.05 * overlap)`
- `search()` now accepts a `step` parameter — domain and intent filtering happen inside the store, not in the pipeline

**Key changes in `rag_pipeline.py`:**
- `is_chunk_relevant()` and post-search filtering removed — `search()` now returns pre-filtered results
- `is_query_related_to_step_v2()` added — uses the domain-filtered search results and score threshold to check step relevance (replaces the old topic-prefix heuristic)
- `ask_with_context()` simplified — receives already-filtered `scored_chunks` from `search()`, no longer needs its own filter pass

**Retrieval debug — before vs after:**

Before (Approach 5.1, "what happens if payment fails?"):
```
0.9530 | create_intent_pending_event_without_completion  ← wrong chunk at rank 1
```

After (Approach 6):
```
1.9167 | create_intent_what_happens_on_completion_failure  ← correct
1.6688 | create_intent_auto_cancel_behavior                ← correct
```

The wrong chunk is gone because intent filtering (`"failure" not in chunk_tags`) excluded it before scoring. The fix wasn't tag weights or scoring tweaks — it was constraining retrieval before scoring.

**What's still weak (will break in production):**

1. **Keyword-based intent detection is brittle.** `detect_intent` uses a hardcoded word list (`fail/fails/failed/failure/error`). Rephrasings like "why was payment cancelled?", "payment didn't complete", "transaction timed out" will not trigger the `failure` intent. The system is still overfitted to specific keywords.

2. **Hard intent filtering is aggressive.** `if intent and intent not in chunk_tags: continue` — if a chunk is mis-tagged or tags are incomplete, correct answers are silently dropped. Tag quality is now a critical dependency.

3. **Tag correctness is assumed, not verified.** The system's retrieval quality now depends entirely on chunks having correct and complete tags. There's no fallback if tagging is wrong — retrieval silently degrades.

4. **No generalization across phrasings.** Queries that need to be tested:
   - "why was payment cancelled?"
   - "payment didn't complete"
   - "transaction failed after processing"

   These will reveal whether the system generalizes or is overfitted to the "failure" keyword.

**Next step:** Replace `detect_intent(query_tokens)` with embedding-based intent classification — `classify_intent_with_embedding(query)` — so "didn't go through", "cancelled", "timed out" all map to the `failure` intent without keyword dependency.

---

## Approach 5.1: Test results — first production-like behavior

**Test results:**

| Case | Step | Query | Expected | Actual | Pass? |
|------|------|-------|----------|--------|-------|
| 1 | `check_intent_response` | "what headers are required?" | API-level answer | Returned correct headers | Yes |
| 2 | `evaluate_status` | "what headers are required?" | Should NOT give API details | Blocked — no leakage | Yes |
| 3 | `check_intent_response` | "what happens if payment fails?" | Failure at creation | Mapped to auto-cancel/failure info | Yes |

All 3 cases pass. Domain filtering, retrieval quality, semantic matching, and gating logic are all working. This is the first time the system behaves like a real product rather than a fragile demo.

**What's working:**
- Domain filtering blocks cross-step queries (Case 2 no longer leaks)
- Semantic matching maps vague queries to correct chunks (Case 3: "payment fails" → `create_intent_what_happens_on_completion_failure`)
- Score-gated fallback correctly distinguishes "filter missed" from "out-of-scope"

**What's still weak (identified in 5.1, fixed in Approach 6):**

1. **Overfitting to the dataset.** Case 3 worked because a chunk named `create_intent_what_happens_on_completion_failure` happened to exist.

2. **No intent abstraction.** The pipeline was `query → embedding → nearest chunk`. Missing layer: `query → intent → retrieval scope`.

3. **Static relevance threshold.** `threshold = 0.55` applied uniformly across domains with different matching needs.

4. **Retrieval ranking issue.** `create_intent_pending_event_without_completion` ranked highest (0.9530) for a failure question — wrong chunk at rank 1, correct answer only appeared because the LLM picked from lower-ranked chunks. Luck, not correctness.

---

## Approach 5: Signal-based retrieval

**What:** Moved from rule-based retrieval (binary include/exclude filters) to signal-based retrieval where multiple weak signals are combined into a composite score, and scores drive all decisions — ranking, filtering, and fallback.

**Key shift:** Previously, scoring happened in `VectorStore` (cosine similarity + boosts), but then `rag_pipeline.py` threw away the scores and applied binary rule filters (`is_relevant` → true/false). Now scores flow through the entire pipeline: `VectorStore.search()` returns `(score, chunk)` tuples, and the pipeline uses those scores for both relevance filtering and threshold guards.

**Changes in `vector_store.py` — multi-signal scoring:**
- Scoring formula: `cosine_similarity * importance_boost * type_boost * tag_boost * keyword_boost`
- importance_boost: high=1.3, medium=1.0, low=0.7 (widened from 1.2/1.0/0.8)
- tag_boost: `1 + (0.15 * tag_overlap)` — counts query-token/tag intersections, scales proportionally
- keyword_boost: `1 + (0.05 * keyword_overlap)` — minor signal from content word matches
- `search()` now returns `(score, chunk)` tuples instead of just chunks
- Pre-computed topic embeddings via `build_topic_index()` for future semantic topic matching

**Changes in `rag_pipeline.py` — conditional fallback:**
- `is_chunk_relevant(chunk, step)` — tag overlap (primary) + topic prefix match (secondary), replaces the old substring check
- `is_query_related_to_step(scored_chunks, step)` — checks if any top chunk shares a topic domain prefix with the step AND has a score above threshold (0.55). This distinguishes "filter missed a relevant chunk" from "query is truly out-of-scope"
- Conditional fallback: only falls back to `scored_chunks[:2]` if `is_query_related_to_step` returns True — otherwise blocks with out-of-scope
- Score threshold (0.6): reuses the score already computed during search instead of re-embedding (eliminates the extra embedding calls from Approach 4)

**Why this over Approach 4:** Approach 4 had two fatal flaws: (1) binary `is_relevant` filter discarded score information — a chunk was either in or out, (2) blind fallback (`context_chunks[:2]`) let any query get answered regardless of step. The system couldn't distinguish "filter missed something" from "query doesn't belong here." Moving to signal-based means scores carry through, and the fallback decision itself is score-gated.

**Result:** All 3 test cases pass — see Approach 5.1 for detailed results.

**Limitations:**
- Tag overlap still depends on naming conventions between `rag_topic` tokens and chunk tags
- Topic prefix match (`step_tokens[0]`) is coarse — "create" would match "create_intent_api" and "create_something_unrelated"
- Pre-computed topic embeddings (`build_topic_index`) exist but aren't used yet in the scoring pipeline
- Threshold values (0.55 for relatedness, 0.6 for final guard) are not tuned

---

## Approach 4.1: Test results — blind fallback defeats flow control

**Test results:**

| Case | Step | Query | Expected | Actual | Pass? |
|------|------|-------|----------|--------|-------|
| 1 | `check_intent_response` | "what headers are required?" | API-level answer | Returned correct headers | Yes |
| 2 | `evaluate_status` | "what headers are required?" | Should NOT give API details | Returned API headers anyway | **No** |
| 3 | `check_intent_response` | "what happens if payment fails?" | Failure at creation | Returned auto-cancel/failure info | Yes |

**What broke:** Case 2 still returns API header details even though the user is on `evaluate_status`, which has nothing to do with headers.

**Root cause:** The blind soft fallback `filtered = context_chunks[:2]` reintroduces the exact problem we were trying to solve. When the relevance filter correctly identifies that "what headers are required?" has no matching chunks for `evaluate_status`, the fallback says "just use the top 2 embedding results anyway" — which are the API header chunks. This cancels the entire flow-scoping layer.

The similarity threshold (0.5) doesn't help here because the query IS semantically similar to the header chunks — it's just not relevant to the *current step*. The problem isn't similarity, it's **scope**. Embedding similarity alone can't enforce step boundaries.

**Key insight:** The system can't distinguish between:
- Query is relevant to this step but the filter missed it (should fallback)
- Query is truly out-of-scope for this step (should block)

**Next step needed:** 
- Conditional fallback that checks whether the fallback chunks are actually related to the current step before allowing them through.
- ❌ filtering-based RAG ➡️ scoring-based RAG ✅

---

## Approach 4: Hybrid topic + tag + similarity filtering with soft fallback

**What:** Replaced the strict `topic == rag_topic` equality check with a three-layer relevance filter: (1) partial topic match — `step.rag_topic in chunk.topic`, (2) tag overlap — tokenize `rag_topic` by underscores and check if any token appears in the chunk's tags, (3) soft fallback — if no chunks pass the filter, take the top 2 most similar candidates from the embedding search instead of immediately returning out-of-scope. Added a similarity threshold guard: if the best chunk's cosine similarity to the query is below 0.5, reject with out-of-scope.

**Key changes:**
- `is_relevant(chunk, step)` function in `rag_pipeline.py` — partial topic match + tag overlap
- Soft fallback: `filtered = context_chunks[:2]` when filter returns empty, preventing total failure
- Similarity threshold: re-embeds query and top chunk, rejects if cosine similarity < 0.5
- `handle_out_of_scope()` still used as final safety net

**Why this over Approach 3:** Approach 3 used exact equality (`chunk.topic == step.rag_topic`) which was over-corrected. The `rag_topic` values in the flow (e.g. `create_intent_response_handling`) never matched the chunk `topic` values (e.g. `create_intent_api`) because they were semantically related but not identical strings. Result: all 3 test cases returned "This question is not relevant" — even when they were relevant. Went from too-loose (Approach 2) to too-strict (Approach 3).

**Result:** Cases 1 and 3 now return relevant answers. The partial match and tag overlap catch chunks that are related but not identically named.

**Limitations:**
- Blind fallback (`context_chunks[:2]`) defeats flow control — any query gets answered regardless of step relevance
- Similarity threshold (0.5) doesn't help because the issue is scope, not similarity
- Partial match is substring-based — can produce false positives
- Tag overlap tokenizes by underscore which is fragile

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
