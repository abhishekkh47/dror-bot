# Evaluation Framework Evolution

Tracks the incremental build-out of the eval harness — what was implemented, what broke, what was discovered, and what it means architecturally.

---

## Step 3.7d: Domain alignment crisis — taxonomy is the real bottleneck

**What:** Evals revealed that retrieval returns nothing ("No relevant context found") for most test cases. The problem is NOT retrieval logic — it's **taxonomy mismatch**. Flow step domains, chunk topics, and eval step domains use different naming conventions that don't align.

**What was discovered:**
- Eval used `domain=["payment_status"]`, but no chunks have topics starting with `payment_status`
- Chunks use topics like `platform_transaction_update_mechanism`, `platform_transaction_definition`
- Switching to `domain=["platform_transaction"]` returned results
- The system now depends heavily on domain contracts — flow domains, chunk domains, and retrieval domains must all align consistently, and currently they don't

**Root cause — taxonomy is structurally wrong:** The current metadata mixes business domains, lifecycle stages, delivery channels, event payload docs, and implementation details into one retrieval namespace. `topic` is overloaded, `tags` are uncontrolled, `type` mixes document category and lifecycle meaning, domains are underspecified.

**What a production system needs — hierarchical retrieval metadata:**

| Concern | Example |
|---------|---------|
| Business domain | payments |
| Capability | create_intent |
| Lifecycle stage | auto_completion |
| Operational state | failed |
| Mechanism | webhook / socket / polling |
| Knowledge type | operational_behavior / transport_payload / api_spec |
| Visibility | public_integrator / internal |

Currently these are all blended into `topic` and `tags`.

**Key insight:** For this use case, **lifecycle stage is more important than semantic similarity**. "Why was payment cancelled?" should prioritize cancellation/completion failure chunks even if webhook cancellation payload chunks are more semantically similar. Lifecycle relevance > embedding similarity. The current architecture only partially enforces this.

**Current domain filtering is too shallow:** `chunk_topic.startswith(domain)` makes topic naming conventions into retrieval logic — fragile. Production systems retrieve by structured metadata fields (`chunk.capability == step.capability`), not string prefix matching.

**What should be prioritized next (not code yet — design first):**

1. Canonical metadata schema redesign
2. Re-chunk + metadata migration
3. Structured retrieval filtering (by fields, not string prefix)
4. Lifecycle-stage-aware retrieval scoring
5. Mechanism-aware suppression (suppress socket/webhook unless asked)
6. Retrieval observability
7. Expanded eval coverage

NOT: more prompt work, reranking, graph DB, agents — those compound taxonomy problems.

**Architectural significance:** The system is no longer building "vector search over docs." It's building **operational knowledge infrastructure**. The weak layer is now knowledge modeling — where enterprise RAG systems either mature properly or collapse into prompt spaghetti.

---

## Step 3.7c: EvalStep contract mismatch — use production models

**What:** The fake `EvalStep` dataclass kept breaking because it missed fields the production pipeline expects (`title`, `description`, `type`, `domain`). Each fix exposed another missing field. This is a classic enterprise testing failure mode — maintaining approximate test objects that drift from production contracts.

**Fix:** Deleted the fake `EvalStep` model entirely. Test cases now import and use the real `Step` model from `app.core.types`. Evals now enforce production contract compatibility instead of approximate copies.

**What this exposed:** The system has evolved enough that fake test inputs break realistically. That's a production maturity signal — the architecture is becoming stateful, structured, and contract-based. Earlier, everything was loosely coupled strings/dicts. Now domain contracts matter.

---

## Step 3.7b: Evals must test the production path, not simplified helpers

**What:** The initial evaluator used `ask(query)` — the basic RAG function that bypasses domain filtering, lifecycle scoping, and flow-aware retrieval. But the production system uses `ask_with_context(query, step)`. Evals were testing a degraded execution path, making results meaningless.

**Fix:** Evaluator now calls `ask_with_context(query, step)`. Test cases include step context with `domain` and `rag_topic`. This means evals now validate: domain filtering, lifecycle scoping, retrieval leakage, and contextual grounding — the actual production behavior.

**Added pipeline error detection:** `evaluate_response()` now catches responses containing "an error occurred while processing your request" and fails the eval immediately — previously a pipeline crash could accidentally pass if the error message happened to contain a required phrase.

**Key principle:** Eval harness must evaluate the **production execution path**, not simplified helper paths. One of the most common mistakes in GenAI eval systems.

---

## Step 3.7a: Initial eval framework — deterministic regression detection

**What:** Introduced the evaluation harness: `test_cases.py` (defines queries with required/forbidden phrases and expected final states), `evaluator.py` (runs each query through the pipeline, checks phrase constraints), `run_eval.py` (runner with pass/fail reporting).

**Why now:** The system has enough layered architecture (retrieval, grounding, contradiction resolution, evidence, prompts, sanitization) that manual observation can't reliably detect regressions. After any architecture change, evals provide automated regression detection.

**What the evals measure (and don't):**

| Evaluates | Does NOT evaluate |
|-----------|-------------------|
| Operational correctness | Exact wording (BLEU/ROUGE) |
| Lifecycle contradiction absence | Generic semantic similarity |
| Internal leakage prevention | Creative generation quality |
| Required operational signals | Response fluency |

**Design choice — intentionally primitive:** Rule-based, phrase-based, deterministic. Do NOT jump to RAGAS, LLM-as-judge, or semantic grading yet. Need stable deterministic constraints before probabilistic evaluation.

**Key realization:** Eval quality now matters more than prompt quality. That's a major maturity transition — the marker of moving from prototype GenAI into production-grade AI engineering.
