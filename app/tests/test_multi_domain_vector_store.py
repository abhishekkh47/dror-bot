from app.core.llm.vector_store import VectorStore

def test_multi_domain_store_loads_all_chunks():
    store = VectorStore([
        "app/data/rag/rag_chunks_create_intent.json",
        "app/data/knowledge_base/authentication.json",
    ])
    # The collection attribute is used in the new ChromaDB implementation
    assert store.collection.count() > 10

def test_authentication_domain_filter():
    store = VectorStore([
        "app/data/rag/rag_chunks_create_intent.json",
        "app/data/knowledge_base/authentication.json",
    ])
    results = store.search("what headers are required?", domain="authentication", top_k=5)
    assert len(results) >= 1
    # All returned chunks should have topics starting with "authentication"
    for _, chunk in results:
        assert chunk["topic"].startswith("authentication"), f"Unexpected topic: {chunk['topic']}"