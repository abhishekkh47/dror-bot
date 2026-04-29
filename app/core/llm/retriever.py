from app.core.llm.vector_store import VectorStore

store = VectorStore("app/data/rag/rag_chunks_create_intent.json")

def retrieve_context(query: str):
    results = store.search(query)

    return "\n\n".join([
        f"[{r['topic']}]\n{r['content']}"
        for r in results
    ])