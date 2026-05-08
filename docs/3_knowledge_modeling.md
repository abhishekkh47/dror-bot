# Phase 4 — Knowledge Modeling & Retrieval Semantics

Continues from `2_normalization_and_distillation.md` (Phase 3: Structured Fact Extraction).

Step 3.7 (Evaluation Framework) exposed the real bottleneck: **retrieval taxonomy mismatch**. Flow domains, chunk topics, and eval domains use different naming conventions. Domain filtering breaks silently. The system has outgrown its metadata architecture.

This phase pauses all retrieval logic, prompt, eval, and sanitizer work. The foundation problem is **metadata architecture** — until that is fixed, every other optimization is unstable.

**Mental shift:** The system is no longer organizing *documents*. It is organizing **operational knowledge units**. That is a fundamentally different design challenge.

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
