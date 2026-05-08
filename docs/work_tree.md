# App Directory Work Tree

```
app/
├── __init__.py
├── main.py                              # FastAPI application entrypoint
│
├── api/
│   ├── __init__.py
│   └── routes.py                        # API endpoints for flow interaction
│
├── core/
│   ├── __init__.py
│   ├── flow_engine.py                   # Flow state transitions and business logic
│   ├── flow_loader.py                   # Loads flow definitions from JSON
│   ├── session_store.py                 # Session state management
│   ├── types.py                         # Pydantic models: Step, Flow, Session
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── chunk_selector.py            # LLM-based two-stage chunk selection
│   │   ├── embedding.py                 # Embedding generation (nomic-embed-text via Ollama)
│   │   ├── lifecycle_facts.py           # LifecycleFacts dataclass, inference, contradiction resolution
│   │   ├── llm.py                       # LLM client wrapper
│   │   ├── operational_distiller.py     # Deterministic noise removal from chunks
│   │   ├── operational_evidence.py      # Converts LifecycleFacts into evidence statements
│   │   ├── prompt.py                    # Structured prompt assembly (system/lifecycle/response rules)
│   │   ├── rag_pipeline.py             # Main RAG orchestration: retrieval → generation
│   │   ├── retriever.py                 # Retrieval interface
│   │   └── vector_store.py              # Embedding storage, similarity search, intent detection
│   │
│   └── rag/
│       ├── chunk_schema.py              # Canonical ChunkMetadata + RAGChunk models (Phase 4)
│
├── data/
│   ├── errors.json                      # Error definitions
│   ├── flows/
│   │   └── payment_execution.json       # Payment processing flow definition
│   └── rag/
│       ├── rag_chunks_create_intent.json   # RAG knowledge chunks (v1 — legacy topic/tags)
│       └── rag_chunks_v2.json              # RAG knowledge chunks (v2 — canonical metadata)
│
├── scripts/
│   ├── __init__.py
│   └── migrate_chunks.py               # Legacy → canonical chunk metadata migration
│
├── tests/
│   ├── __init__.py
│   ├── 1_basic_query_retrieval_rag.py   # Basic embedding retrieval tests
│   ├── 2_context_and_query_retrieval_rag.py  # Context-aware retrieval tests
│   └── 3_intent_based_filter_ranking_rag.py  # Semantic intent detection tests
│   └── evals/
│           ├── __init__.py
│           ├── eval_evolution.md         # Eval framework evolution documentation
│           ├── evaluator.py             # Regression evaluator: phrase checks + pipeline error detection
│           ├── run_eval.py              # Eval runner with pass/fail reporting
│           └── test_cases.py            # Test case definitions with Step context
│
└── utils/
    ├── __init__.py
    ├── constants.py                     # INTENT_DEFINITIONS, TAG_PRIORITY, CRITICAL_TAGS
    ├── logger.py                        # Logging configuration
    ├── patterns.py                      # Regex patterns
    └── prompts.py                       # Prompt utilities
```
