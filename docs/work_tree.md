# App Directory Work Tree

```text
app/
├── main.py                              # FastAPI ASGI application entrypoint
├── api/
│   └── routes.py                        # API endpoints (/query, /query/stream)
├── core/
│   ├── session_store.py                 # SQLite session and history tracking
│   ├── types.py                         # Pydantic models (QueryRequest, QueryResponse)
│   ├── cache/
│   │   ├── cache_keys.py                # Cache key generation using query + history
│   │   ├── redis_client.py              # Redis connection pool management
│   │   └── response_cache.py            # Redis get/set abstraction layer
│   ├── knowledge/
│   │   ├── domain_classifier.py         # LLM-based query domain classification
│   │   └── scope_guard.py               # Enforces DrorPay domain boundaries
│   ├── llm/
│   │   ├── embedding.py                 # Ollama text embeddings generator
│   │   ├── llm.py                       # OpenAI chat completions and streaming wrapper
│   │   ├── qa_pipeline.py               # Active RAG orchestrator for Developer Docs
│   │   ├── retriever.py                 # VectorStore initialization and configs
│   │   └── vector_store.py              # ChromaDB client and similarity search
│   ├── observability/
│   │   ├── telemetry.py                 # Telemetry dataclasses
│   │   └── telemetry_logger.py          # Structured JSON logging for telemetry
│   ├── rag/
│   │   ├── chunk_schema.py              # Chunk metadata and schema models
│   │   └── ingestion_service.py         # Dynamic markdown ingestion and text slicing
│   └── security/
│       ├── pii_redactor.py              # Sensitive data and PII filtering
│       ├── rate_limiter.py              # SlowAPI rate limiting configuration
│       └── request_guard.py             # Malicious payload detection
├── data/
│   ├── knowledge_base/                  # Static JSON knowledge base files
│   └── rag/                             # Raw RAG chunk dumps
├── scripts/
│   ├── seed_chroma.py                   # CLI tool to load JSON into ChromaDB
│   └── sync_markdown.py                 # CLI tool to ingest Markdown into ChromaDB
├── tests/                               # Active unit tests
│   ├── test_domain_classifier.py
│   ├── test_multi_domain_vector_store.py
│   ├── test_qa_pipeline.py
│   └── test_scope_guard.py
└── utils/
    ├── constants.py                     # App-wide configuration constants
    ├── logger.py                        # Custom structured logging setup
    ├── patterns.py                      # Reusable regex patterns
    └── prompts.py                       # LLM Prompt string templates
```
