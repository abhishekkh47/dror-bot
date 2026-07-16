from app.core.llm.vector_store import VectorStore

KNOWLEDGE_FILES = [
    "app/data/rag/rag_chunks_create_intent.json",
    "app/data/knowledge_base/authentication.json",
    "app/data/knowledge_base/platform_setup.json",
    "app/data/knowledge_base/transactions.json",
    "app/data/knowledge_base/webhooks.json",
    "app/data/knowledge_base/sockets.json",
    "app/data/knowledge_base/refunds.json",
    "app/data/knowledge_base/disputes.json",
    "app/data/knowledge_base/troubleshooting.json",
]

# We now rely purely on the Chroma DB connection (decoupled runtime).
# To populate data, run `python3 app/scripts/seed_chroma.py`
store = VectorStore(path=None)

def retrieve_context(query: str, rag_topic: str = None):
    results = store.search(query, top_k=8)

    if rag_topic:
        # filter by topic first
        filtered = [r for r in results if r['topic'] == rag_topic]

        if filtered:
            results = filtered
        else:
            # ⚠️ DO NOT fallback blindly
            results = []
    # If topic match fails → it will fallback to full results

    return "\n\n".join([
        f"[{r['topic']}]\n{r['content']}"
        for r in results
    ])