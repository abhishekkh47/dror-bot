# Phase 4 — Knowledge Modeling & Retrieval Semantics

Continues from `2_normalization_and_distillation.md` (Phase 3: Structured Fact Extraction).

Step 3.7 (Evaluation Framework) exposed the real bottleneck: **retrieval taxonomy mismatch**. Flow domains, chunk topics, and eval domains use different naming conventions. Domain filtering breaks silently. The system has outgrown its metadata architecture.

This phase pauses all retrieval logic, prompt, eval, and sanitizer work. The foundation problem is **metadata architecture** — until that is fixed, every other optimization is unstable.

**Mental shift:** The system is no longer organizing *documents*. It is organizing **operational knowledge units**. That is a fundamentally different design challenge.

---

## Step 4.2: Chunk metadata migration

**Category:** Knowledge Base Normalization

**What:** Migrate existing chunks from loosely-tagged embeddings (`topic` + `tags`) to structured `RAGChunk` objects using the canonical `ChunkMetadata` schema defined in Step 4.1. This is where the system transitions from topic-string-driven retrieval to metadata-semantics-driven retrieval.

**The problem with the current structure:**

Chunks currently look like:
```json
{
  "topic": "platform_transaction_update_mechanism",
  "tags": ["socket", "webhook", "polling"]
}
```

This mixes lifecycle semantics, transport semantics, and operational semantics into one retrieval surface. That is structurally wrong. Retrieval filtering cannot be precise, transport chunks leak into operational queries, and lifecycle-stage retrieval depends on topic naming conventions instead of explicit metadata fields.

**What we are building:**

A canonical chunk schema (`app/core/rag/chunk_schema.py`, already created in Step 4.1) that ALL chunks must follow:

```python
class RAGChunk(BaseModel):
    id: str
    metadata: ChunkMetadata  # structured retrieval semantics
    tags: List[str] = []     # lightweight ranking hints
    content: str
```

Key design principle: `metadata` is separated from `tags`. Metadata = structured retrieval semantics. Tags = lightweight ranking hints. The current system incorrectly mixes them.

**Migration approach — inference script (`scripts/migrate_chunks.py`):**

A deterministic migration script that transforms legacy chunks into canonical `RAGChunk` objects. The script infers metadata from the old `topic` and `tags` fields:

- **Capability inference:** `"intent" in topic` → `create_intent`, `"transaction" in topic` → `platform_transaction`, `"completion" in topic` → `auto_completion`
- **Lifecycle inference:** `"validation" in topic` → `validation`, `"completion" in topic` → `auto_completion`, `"cancel" in topic` → `cancellation`
- **Mechanism inference:** `"webhook" in tags` → `webhook`, `"socket" in tags` → `socket`, `"polling" in tags` → `polling`
- **Knowledge type inference:** chunks with a transport mechanism → `transport_behavior`, others → `operational_behavior`
- **Importance inference:** chunks tagged with `failure`, `rollback`, `cancellation` → `high`

**Expected output format:**
```json
{
  "id": "...",
  "metadata": {
    "business_domain": "payments",
    "capability": "platform_transaction",
    "lifecycle_stage": "auto_completion",
    "knowledge_type": "operational_behavior",
    "artifact_type": "explanation",
    "importance": "high"
  },
  "tags": ["failure", "rollback"],
  "content": "..."
}
```

**Migration rules:**
- Do NOT overwrite old chunks. Output goes to `data/rag_chunks_v2.json`. Keep v1 and v2 side-by-side
- This first migration is intentionally imperfect — the goal is deterministic structure first, not perfect semantics. Inference will be refined later
- The migration script is temporary infrastructure — its job is to normalize legacy data, bootstrap canonical schema, and expose taxonomy gaps

**The architectural win:** Previously, topic naming WAS retrieval architecture. After migration, metadata semantics ARE retrieval architecture. Retrieval filtering can now use structured field matching (`chunk.capability == step.capability`) instead of string prefix matching (`topic.startswith(domain)`).

**What NOT to do yet:** Do NOT rewrite retrieval logic, change embeddings, add reranking, or modify prompts. Normalized knowledge structure must exist before retrieval can evolve safely.

**Next step:** Step 4.3 — Structured Retrieval Filtering Engine. Retrieval stops depending on topic prefixes. Filtering becomes metadata-driven. Lifecycle-stage filtering becomes explicit. Transport suppression becomes deterministic. That is where retrieval quality will jump substantially.

---

## Step 4.1: Canonical knowledge taxonomy

**Category:** Knowledge Modeling & Retrieval Semantics

**What:** Defined the canonical retrieval taxonomy (`docs/rag_taxonomy.md`) and the canonical chunk metadata schema (`app/core/rag/chunk_schema.py`). This replaces the semi-random topic naming conventions with explicit, structured retrieval semantics. Every chunk now explicitly declares what capability it belongs to, what lifecycle stage it belongs to, what kind of knowledge it is, whether it is operational vs transport detail, and whether it should participate in normal retrieval.

**Why this step exists — the taxonomy problem:**

The current system retrieves based on topic names like:
- `create_intent_auto_completion_stage`
- `platform_transaction_update_mechanism`
- `socket_payment_failed_payload`

These are inconsistent abstraction levels, mixed semantics, mixed mechanisms, mixed lifecycle scopes. The system mixes business domains, lifecycle stages, delivery channels, event payload docs, and implementation details into overlapping metadata. `topic` is overloaded, `tags` are uncontrolled, `type` mixes document category and lifecycle meaning, and domains are underspecified.

**The canonical taxonomy — 9 explicit retrieval dimensions:**

| Field | Semantic question it answers | Examples |
|-------|------------------------------|----------|
| `business_domain` | What product/business area? | payments, refunds, disputes, wallets |
| `capability` | What workflow/API capability? | create_intent, payment_status, auto_completion |
| `lifecycle_stage` | What operational phase? | validation, transaction_creation, auto_completion, cancellation |
| `operational_state` | What state does this represent? | pending, completed, failed, cancelled |
| `knowledge_type` | What is the semantic role? | api_spec, operational_behavior, business_rule, transport_behavior |
| `artifact_type` | What is the structural format? | flow, payload, schema, rules, explanation |
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
