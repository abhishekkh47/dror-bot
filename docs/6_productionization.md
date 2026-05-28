# Phase 7 — Productionization

Continues from `5_conversational_memory.md` (Phase 6: Conversational Memory & Investigation Continuity).

Phase 6 delivered a complete memory subsystem: stateful operational memory, investigation continuity, memory-aware retrieval boosting, summarization, reset governance, and normalization. The internal retrieval/reasoning architecture is now robust.

**The transition:** Architecture experimentation → Operational system engineering.

Internal scoring, governance, and retrieval infrastructure have reached sufficient maturity. The remaining risks are no longer about retrieval intelligence — they are about **production engineering**: persistence, latency, caching, observability, prompt efficiency, and operational safety.

**Current risk assessment:**

| Risk | Severity |
|------|----------|
| Memory contamination | Mostly solved |
| Retrieval instability | Mostly solved |
| Hallucination governance | Good enough |
| Orchestration coherence | Good |
| Latency growth | HIGH |
| Prompt bloat | HIGH |
| Eval weakness | HIGH |
| No real observability | HIGH |
| No production persistence | HIGH |
| No async orchestration | HIGH |
| No caching | HIGH |

**Key principle:** No more internal retrieval scores, validators, or governance layers. Every step in this phase delivers operational production infrastructure.

---

## Step 6.1: Redis session memory

**Category:** Production Persistence

**What:** Replaced process-local in-memory session storage (`MEMORY_STORE = {}`) with Redis-backed session memory. Sessions now persist across server restarts, support multi-instance deployments, and expire automatically via TTL.

**The problem — process-local state in a production system:**

The entire memory subsystem (lifecycle facts, operational history, investigation summaries, discussed topics) was stored in a Python `dict` inside the process. This means:

- Server restart = all investigation memory lost
- Multiple workers = inconsistent memory across instances
- No TTL = memory accumulates indefinitely
- No persistence = debugging and auditing impossible

For a payments/compliance support system, losing investigation state mid-session is operationally unacceptable.

**What was built:**

**`app/core/cache/redis_client.py`** — Production Redis client:

| Feature | Implementation |
|---------|---------------|
| Environment-based config | `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` from env vars |
| Connection pooling | `ConnectionPool` with `max_connections=10` |
| Timeout protection | `socket_connect_timeout=3s`, `socket_timeout=5s` |
| Retry on timeout | `retry_on_timeout=True` |
| Health check | `is_redis_available()` using `PING` |

All settings configurable via environment variables with safe defaults (localhost:6379, no password, 1-hour TTL).

**`app/core/memory/memory_store.py`** — Hardened session storage:

| Feature | Implementation |
|---------|---------------|
| Redis persistence | `SessionMemory` serialized via `model_dump_json()` / `model_validate_json()` |
| Configurable TTL | `MEMORY_TTL_SECONDS` env var (default: 3600 = 1 hour) |
| Graceful degradation | Falls back to in-memory `dict` if Redis is unavailable |
| Error isolation | Redis connection/timeout errors caught per-operation, never crash the pipeline |
| Delete support | `delete_session_memory(session_id)` for explicit cleanup |
| Key namespacing | `drorbot:memory:{session_id}` prefix for multi-app Redis sharing |

**Graceful degradation pattern:**

```python
def get_session_memory(session_id):
    if is_redis_available():
        try:
            raw = redis_client.get(f"{MEMORY_PREFIX}:{session_id}")
            return SessionMemory.model_validate_json(raw)
        except (ConnectionError, TimeoutError):
            logger.warning("Redis read failed, falling back")
    return _fallback_store.get(session_id)
```

The system **never crashes** because Redis is down. It logs the failure and degrades to in-memory state — maintaining service availability while losing cross-restart persistence.

**Also fixed in this step — memory retrieval boost aggression:**

| Signal | Before | After |
|--------|--------|-------|
| Topic continuity boost | +0.20 | +0.08 |
| Lifecycle continuity boost | +0.15 | +0.05 |

Original values were too aggressive for production — they created retrieval drift in long investigations where old topics permanently dominated new evidence. Reduced values maintain investigation continuity without overriding fresh evidence signals.

**What this changes:**

| Before | After |
|--------|-------|
| `MEMORY_STORE = {}` in process | Redis with connection pooling |
| Restart = lost memory | Sessions persist across restarts |
| Single-worker only | Multi-instance safe (shared Redis) |
| No expiration | Automatic TTL expiration |
| Redis failure = crash | Graceful fallback to in-memory |
| Hardcoded connection | Environment-based configuration |
| No cleanup API | `delete_session_memory()` for explicit removal |

**Environment variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_DB` | `0` | Redis database index |
| `REDIS_PASSWORD` | `None` | Redis auth password |
| `MEMORY_TTL_SECONDS` | `3600` | Session memory expiration (seconds) |

**Dependency added:** `redis>=5.0.0` in `requirements.txt`.

**What this step did NOT change:**
- No response caching yet — only session memory is persisted
- No async Redis operations — synchronous calls (sufficient for current load)
- No Redis Sentinel or cluster support — single-node Redis is the starting point
- No memory migration tooling — existing in-memory sessions are lost on upgrade (acceptable: sessions are ephemeral by nature)

---

## Step 6.2: Response & retrieval caching

**Category:** Latency & Cost Optimization

**What:** Introduced reliability-aware response caching. Repeated queries for the same step now return cached results instantly — skipping retrieval, orchestration, and LLM generation entirely. Only stable, high-confidence, conflict-free responses are cached. Unreliable, ambiguous, or degraded responses are never cached.

**The problem — full pipeline recomputation on every request:**

Every request triggers the entire orchestration chain: vector search → filtering → lifecycle extraction → chunk selection → distillation → reliability scoring → memory loading → prompt assembly → LLM generation → sanitization. For repeated operational questions (common in support systems), this is unnecessary compute duplication that wastes tokens, increases latency, and scales poorly under concurrency.

**Key insight:** Production AI systems optimize repeated operational patterns, not merely single-query correctness. The same integration question asked by different users against the same step should not trigger separate LLM calls.

**What was built:**

**`app/core/cache/cache_keys.py`** — Deterministic cache key generation:

```python
raw = f"{query}|{step.id}|{step.rag_topic}"
hashed = hashlib.md5(raw.encode()).hexdigest()
return f"drorbot:response:{hashed}"
```

Key is scoped to `query + step.id + step.rag_topic` — same question at the same step always hits the same cache entry. Different steps or different queries always miss. Session-independent by design: operational guidance for the same step/query is identical across users.

**`app/core/cache/response_cache.py`** — Redis-backed response cache:

| Feature | Implementation |
|---------|---------------|
| Configurable TTL | `RESPONSE_CACHE_TTL_SECONDS` env var (default: 1800 = 30 min) |
| Redis health check | `is_redis_available()` before read/write |
| Error isolation | Connection/timeout errors caught per-operation, return `None` on failure |
| Graceful degradation | Cache miss on Redis failure — pipeline proceeds normally |
| JSON serialization | `ExecutionResult` serialized via `model_dump()` / `json.dumps()` |

**`app/core/cache/cache_policy.py`** — Reliability-aware cache governance:

A response is cacheable ONLY when ALL conditions are met:

| Condition | Why |
|-----------|-----|
| `response_mode == "normal"` | Fallback/clarification responses should not be cached |
| `response_reliability_score >= 75` | Low-reliability responses may change with better evidence |
| No `operational_conflicts` | Conflicting evidence means the answer may be wrong |
| No `operational_ambiguities` | Ambiguous state should trigger fresh investigation, not cached answers |

This is **reliability-aware caching** — only stable, trustworthy operational guidance gets cached. Ambiguous troubleshooting, low-confidence retrieval, and degraded responses always trigger fresh computation.

**Pipeline integration in `rag_pipeline.py`:**

Cache check happens early — after memory loading but before any retrieval:

```python
cache_key = build_response_cache_key(query=query, step=step)
cached = get_cached_response(cache_key)
if cached:
    return ExecutionResult(**cached)
```

Cache save happens at the end — only if the policy allows:

```python
execution_result = ExecutionResult(...)
if should_cache_response(execution_result):
    save_cached_response(cache_key, execution_result.model_dump())
```

**What this changes:**

| Before | After |
|--------|-------|
| Every request = full pipeline | Repeated queries = instant cache hit |
| Redundant LLM calls on identical questions | Single LLM call per unique query/step |
| Latency scales linearly with requests | Repeated requests are O(1) Redis lookup |
| Token cost scales linearly | Token cost scales with unique queries only |
| No response persistence | Responses persist for 30 min in Redis |

**What is explicitly NOT cached:**
- Fallback responses (`response_mode != "normal"`)
- Low-reliability responses (`response_reliability_score < 75`)
- Responses with operational conflicts
- Responses with operational ambiguities
- Error/exception responses

**Environment variables:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `RESPONSE_CACHE_TTL_SECONDS` | `1800` | Response cache expiration (seconds) |

**What this step did NOT change:**
- No retrieval-level caching — only full response caching (retrieval cache is a separate concern)
- No cache invalidation on knowledge base updates — TTL expiration handles staleness for now
- No cache warming or precomputation — reactive caching only
- No per-user response variation — cache is session-independent (correct for operational guidance)

---

## Step 6.3: Observability & metrics pipeline

**Category:** Production AI Telemetry

**What:** Introduced centralized orchestration telemetry. Every request now emits a structured telemetry event containing retrieval metrics, reasoning metrics, latency measurements, reliability scores, and cache performance signals. Both cache hits and full pipeline executions are instrumented.

**The problem — invisible degradation:**

The system computes confidence, coherence, ambiguity, reliability, retry behavior, and fallback decisions — but all of this exists only inside `ExecutionResult` objects and scattered log messages. There is no centralized way to see:
- How often fallbacks happen
- Which domains fail most
- Cache hit rate
- Ambiguity frequency
- Retrieval instability trends
- Latency bottlenecks

Enterprise AI systems fail because of invisible degradation, not bad architecture.

**What was built:**

**`app/core/observability/telemetry.py`** — `build_telemetry_event()`:

Builds a structured telemetry dict from every `ExecutionResult`. Captures:

| Signal | Source | Why |
|--------|--------|-----|
| `query` | Request | Query identification (for pattern analysis) |
| `step_id` | Step | Domain/flow segmentation |
| `rag_topic` | Step | Knowledge domain tracking |
| `cache_hit` | Pipeline | Cache effectiveness measurement |
| `retrieval_confidence` | ExecutionResult | Retrieval quality tracking |
| `response_mode` | ExecutionResult | Fallback/clarification rate tracking |
| `quality_score` | ExecutionResult | Response quality trends |
| `retrieval_stability_score` | ExecutionResult | Retrieval consistency monitoring |
| `lifecycle_coherence_score` | ExecutionResult | Evidence coherence trends |
| `response_reliability_score` | ExecutionResult | Overall reliability monitoring |
| `retry_attempted` | ExecutionResult | Retry rate tracking |
| `reasoning_issue_count` | ExecutionResult | Reasoning failure frequency |
| `operational_conflict_count` | ExecutionResult | Conflict detection rate |
| `operational_ambiguity_count` | ExecutionResult | Ambiguity frequency |
| `selected_chunk_count` | ExecutionResult | Retrieval volume monitoring |
| `latency_ms` | Pipeline timing | Latency bottleneck detection |

**`app/core/observability/telemetry_logger.py`** — `log_telemetry_event()`:

Emits telemetry events as structured JSON via the application logger under `RAG_TELEMETRY` message type. Designed for easy downstream parsing by log aggregation systems (ELK, Datadog, CloudWatch).

**Pipeline integration in `rag_pipeline.py`:**

Two telemetry emission points:

1. **Cache hit path** — emits telemetry with `cache_hit=True` and cache-lookup latency, then returns early. Without this, cached requests would be invisible to monitoring.

2. **Full pipeline path** — emits telemetry with `cache_hit=False` and total orchestration latency after `ExecutionResult` construction.

Latency measured from `request_start = time.time()` set immediately after entering the `try` block.

**What this changes:**

| Before | After |
|--------|-------|
| Telemetry scattered across log messages | Centralized structured telemetry events |
| Cache hits invisible | Cache hits emit telemetry with `cache_hit=True` |
| No latency measurement | End-to-end latency captured per request |
| Cannot measure fallback rate | `response_mode` tracked per event |
| Cannot detect retrieval degradation | Confidence/stability/coherence tracked per event |
| Cannot measure cache effectiveness | `cache_hit` boolean in every event |

**What is explicitly NOT logged (security):**
- Raw user secrets or payment credentials
- Full chunk content or prompt text
- Sensitive session memory payloads

Telemetry contains operational signals only.

**What this step did NOT change:**
- No Prometheus/Grafana integration yet — structured logs are the starting point
- No aggregation or dashboarding — that requires a log pipeline consumer
- No alerting rules — thresholds and alerting come after baseline measurement
- No distributed tracing — single-service telemetry is sufficient for current architecture

**Productionization roadmap — remaining steps:**

| Step | Focus | Priority |
|------|-------|----------|
| 6.4 | Prompt size governance | HIGH — token budgeting and context truncation |
| 6.5 | Real eval dataset | HIGH — 100-500 realistic support questions |
| 6.6 | Human escalation governance | HIGH — when to stop answering |
