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

---

## Step 6.4: Async orchestration pipeline

**Category:** Concurrency & Latency Engineering

**What:** Converted the entire orchestration pipeline from blocking sequential execution to async Python. Redis operations use `redis.asyncio`, the core `ask_with_context()` function is now `async`, and non-critical side effects (memory persistence, cache saves, telemetry) are backgrounded via `asyncio.create_task()` so they never block response delivery.

**The problem — sequential latency stacking:**

The orchestration pipeline executes ~10 stages serially: memory load → cache check → retrieval → filtering → scoring → prompt build → LLM generation → sanitization → memory save → telemetry. As traffic grows, this creates latency stacking — every stage waits for the previous one, even when some operations (memory saves, telemetry, cache writes) don't need to complete before the response is returned.

Redis calls (memory load, cache check, memory save, cache save) were synchronous, blocking the Python event loop and preventing concurrent request handling.

**What was changed:**

**`app/core/cache/redis_client.py`** — Async Redis client:

| Before | After |
|--------|-------|
| `import redis` | `from redis.asyncio import Redis` |
| `redis.ConnectionPool(...)` | `Redis(...)` with async connection pool |
| `def is_redis_available()` | `async def is_redis_available()` |
| `redis_client.ping()` | `await redis_client.ping()` |

**`app/core/memory/memory_store.py`** — All functions async:

| Function | Change |
|----------|--------|
| `get_session_memory()` | `async def` + `await redis_client.get()` |
| `save_session_memory()` | `async def` + `await redis_client.set()` |
| `delete_session_memory()` | `async def` + `await redis_client.delete()` |

Redis exception handling changed from `import redis as redis_lib` to `from redis import exceptions as redis_exceptions` for cleaner async compatibility.

**`app/core/cache/response_cache.py`** — All functions async:

| Function | Change |
|----------|--------|
| `get_cached_response()` | `async def` + `await redis_client.get()` |
| `save_cached_response()` | `async def` + `await redis_client.set()` |

**`app/core/observability/telemetry_logger.py`** — Added async wrapper:

| Function | Purpose |
|----------|---------|
| `log_telemetry_event()` | Sync version (preserved for backwards compatibility) |
| `async_log_telemetry_event()` | Async-compatible wrapper for `asyncio.create_task()` |

**`app/core/llm/rag_pipeline.py`** — Major async conversion:

`ask_with_context()` converted to `async def`. Three categories of changes:

1. **Critical-path awaits** (must complete before response):
   - `await get_session_memory(session_id)` — need memory before retrieval
   - `await get_cached_response(cache_key)` — need cache result before deciding to compute

2. **Backgrounded side effects** (do not block response delivery):
   ```python
   asyncio.create_task(async_log_telemetry_event(telemetry_event))
   asyncio.create_task(save_session_memory(session_memory))
   asyncio.create_task(save_cached_response(cache_key, payload))
   ```

3. **Unchanged** (CPU-bound, no I/O):
   - `build_retrieval_context()` — vector search + filtering (future async candidate)
   - `generate_response()` — LLM call (future async candidate)
   - All scoring, validation, sanitization functions

**Callers updated:**

| File | Change |
|------|--------|
| `app/api/routes.py` | `def process_input()` → `async def process_input()` + `await ask_with_context()` |
| `app/tests/evals/evaluator.py` | Core logic moved to `async _run_all_evals_async()`, sync `run_all_evals()` wraps with `asyncio.run()` |

FastAPI natively supports `async def` endpoints, so the route conversion is seamless.

**What the critical path looks like now:**

```
await memory_load  →  await cache_check  →  retrieval  →  generation  →  return response
                                                                              ↓ (backgrounded)
                                                                        memory_save
                                                                        cache_save
                                                                        telemetry
```

Non-critical writes no longer block response delivery.

**What this changes:**

| Before | After |
|--------|-------|
| Blocking sequential execution | Async orchestration with backgrounded side effects |
| Redis calls block event loop | Redis calls are non-blocking `await` |
| Memory save blocks response | Memory save backgrounded via `create_task` |
| Cache save blocks response | Cache save backgrounded via `create_task` |
| Telemetry blocks response | Telemetry backgrounded via `create_task` |
| Single concurrent request per worker | Multiple concurrent requests per worker |

**What this step did NOT change:**
- `build_retrieval_context()` and `generate_response()` remain synchronous — these are the heaviest operations and will need async conversion in a future step (likely with `httpx` async for LLM calls)
- No distributed task queue (Celery/Kafka) — `asyncio.create_task` is sufficient for current single-process concurrency
- No connection pool tuning beyond defaults — Redis async pool handles this automatically
- Backgrounded tasks may fail silently — acceptable for telemetry/cache; memory save failures degrade gracefully via the existing fallback store

---

## Step 6.5: Prompt compaction & token governance

**Category:** Prompt Efficiency Engineering

**What:** Introduced deterministic prompt compaction that bounds all prompt inputs before context assembly. Chunks, operational evidence, and memory findings are now truncated to configurable limits, preventing unbounded prompt growth as features accumulate.

**The problem — accumulation-driven prompt architecture:**

The prompt currently injects: lifecycle rules, operational evidence, memory context, distilled chunks, response constraints, response patterns, confidence policy, and lifecycle timeline. Each feature adds more context. Without governance, prompts grow monotonically — eventually causing:

- Token budget overruns and increased latency
- Context dilution (model loses focus on high-signal evidence)
- Higher hallucination rates (more noise for the model to filter)
- Escalating API costs

**Key principle:** Prompt quality depends on signal density, not maximum context size. Past a certain point, bigger prompts reduce reasoning quality.

**What was built:**

**`app/core/llm/prompt_budget.py`** — Configurable prompt limits:

| Constant | Value | What it bounds |
|----------|-------|---------------|
| `MAX_CONTEXT_CHUNKS` | 5 | Distilled evidence chunks in the prompt |
| `MAX_OPERATIONAL_EVIDENCE` | 5 | Operational evidence statements |
| `MAX_MEMORY_FINDINGS` | 3 | Investigation findings from memory |

**`app/core/llm/prompt_compactor.py`** — `compact_prompt_inputs()`:

Takes distilled chunks, operational evidence, and memory summary. Returns bounded versions:
- Chunks truncated to top `MAX_CONTEXT_CHUNKS` (already ranked by relevance from retrieval)
- Evidence truncated to top `MAX_OPERATIONAL_EVIDENCE`
- Memory summary fields individually bounded (`active_lifecycle_states[:3]`, `major_operational_findings[:MAX_MEMORY_FINDINGS]`, `active_topics[:3]`)

Deterministic truncation, not semantic compression. Relies on upstream ranking to ensure the highest-signal items are at the front.

**Pipeline integration — ordering fix:**

Compaction now runs **before** `build_structured_context()`, not after. The structured context block sent to the prompt uses compacted inputs:

```
compacted = compact_prompt_inputs(...)     # bound the inputs
distilled_chunks = compacted[...]          # reassign to compacted
operational_evidence = compacted[...]
memory_summary = compacted[...]
context = build_structured_context(...)    # build from compacted inputs
```

**What this changes:**

| Before | After |
|--------|-------|
| All retrieved chunks injected into prompt | Top 5 chunks only |
| All operational evidence injected | Top 5 evidence statements only |
| Full memory summary injected | Bounded to 3 findings, 3 states, 3 topics |
| Prompt size grows with every feature | Prompt size bounded by budget constants |
| No governance over prompt inputs | Configurable limits per input type |

**What this step did NOT change:**
- No token counting yet — limits are item-count-based, not token-based (sufficient for current prompt sizes)
- No semantic compression — simple truncation relies on upstream relevance ranking
- No dynamic budgeting based on query complexity — static limits for now
- Lifecycle facts and response constraints are not compacted — these are small and critical

---

## Step 6.6: Human escalation governance

**Category:** Operational Safety & Escalation Control

**What:** Introduced explicit escalation boundaries that detect when the AI should stop troubleshooting and delegate to human support. Escalation triggers on sensitive operational patterns (fraud, chargebacks, compliance), excessive ambiguity, or heavy operational conflicts. Escalated responses are never cached and are tracked in telemetry.

**The problem — AI that always tries to answer:**

The system previously assumed it should always attempt to troubleshoot, regardless of topic sensitivity. For a payments/compliance support system, this creates risk: the AI may attempt to diagnose billing disputes, explain compliance outcomes, infer account restrictions, or troubleshoot fraud-related flows using speculative reasoning. These situations require human investigation, not autonomous AI troubleshooting.

**Key principle:** Trustworthy operational AI systems must know when NOT to answer. Safe delegation is more important than maximum automation.

**What was built:**

**`app/core/escalation/escalation_policy.py`** — `should_escalate_to_human()`:

Three escalation triggers:

| Trigger | Condition | Why |
|---------|-----------|-----|
| Sensitive patterns | Query matches any of 9 escalation patterns | Fraud, chargebacks, compliance, KYC, missing funds, unauthorized transactions — all require human investigation |
| Excessive ambiguity | `response_reliability_score < 40` | System confidence is too low to provide trustworthy guidance |
| Heavy conflicts | `operational_conflicts >= 2` | Multiple conflicting evidence signals — AI cannot resolve safely |

Escalation patterns: `missing funds`, `money not received`, `account restricted`, `compliance review`, `kyc rejected`, `fraud`, `chargeback`, `legal issue`, `unauthorized transaction`.

**`app/core/escalation/escalation_response.py`** — `build_escalation_response()`:

Returns a safe, neutral escalation message directing the user to contact support with transaction details. Deliberately does not speculate about the issue or offer partial troubleshooting.

**`app/core/types.py`** — `ExecutionResult` updated:

Added `human_escalation_required: bool = False`. Enables downstream systems (API, telemetry, caching) to react to escalation state.

**Pipeline integration in `rag_pipeline.py`:**

Escalation check runs after `ExecutionResult` construction — after the full pipeline has computed all scoring signals. If triggered, the response is overridden:

```python
if should_escalate_to_human(query, execution_result):
    execution_result.response = build_escalation_response()
    execution_result.human_escalation_required = True
```

**Cross-cutting integration — escalation-aware caching and telemetry:**

**`app/core/cache/cache_policy.py`** — Escalated responses are never cached. Without this, a fraud-related query that happens to retrieve well (high reliability, normal mode) would cache the escalation message, causing identical future queries to return the escalation response even after patterns are updated.

**`app/core/observability/telemetry.py`** — `human_escalation_required` added to telemetry events. Enables monitoring escalation rate, identifying which query patterns trigger escalation most, and detecting escalation drift.

**What this changes:**

| Before | After |
|--------|-------|
| AI always attempts to answer | AI detects escalation-sensitive situations |
| Fraud/compliance queries get speculative answers | Fraud/compliance queries trigger safe handoff |
| Low-reliability responses still delivered | Very low reliability triggers escalation |
| Heavy conflicts still produce responses | Multiple conflicts trigger escalation |
| Escalation invisible to telemetry | Escalation rate trackable via telemetry |
| Escalated responses could be cached | Escalated responses explicitly excluded from cache |

**What this step did NOT change:**
- No ticket routing or support workflow automation — escalation triggers a safe response, not a support ticket
- No per-domain escalation tuning — all escalation patterns use the same threshold
- No escalation cooldown or rate limiting — every matching query triggers escalation independently
- No semantic escalation detection — pattern matching only (sufficient for known sensitive terms)

**Current architecture status after Phase 7:**

| Capability | Status |
|------------|--------|
| Stateful investigations | Done |
| Reliability governance | Done |
| Async orchestration | Done |
| Production caching | Done |
| Prompt governance | Done |
| Observability | Done |
| Human escalation boundaries | Done |

**The productionization phase is now complete.** The system has transitioned from architecture experimentation to operational system engineering. Remaining frontiers are: real eval datasets, admin observability dashboards, abuse prevention, rate limiting, deployment pipelines, autoscaling, and load testing.
