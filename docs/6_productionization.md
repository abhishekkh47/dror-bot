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

**Productionization roadmap — remaining steps:**

| Step | Focus | Priority |
|------|-------|----------|
| 6.2 | Response caching | HIGH — reduce redundant LLM calls |
| 6.3 | Prompt size governance | HIGH — token budgeting and context truncation |
| 6.4 | Real eval dataset | HIGH — 100-500 realistic support questions |
| 6.5 | Observability dashboard | HIGH — metrics, rates, latency tracking |
| 6.6 | Human escalation governance | HIGH — when to stop answering |
