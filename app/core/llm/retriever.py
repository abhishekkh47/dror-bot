from app.core.llm.vector_store import VectorStore

store = VectorStore("app/data/rag/rag_chunks_create_intent.json")

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