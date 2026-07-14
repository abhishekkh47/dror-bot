import os
import json
import sys

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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

def seed_database():
    print("Initializing VectorStore for seeding...")
    store = VectorStore(path=None)
    
    existing_files = [f for f in KNOWLEDGE_FILES if os.path.exists(f)]
    
    if not existing_files:
        print("No JSON knowledge files found. Nothing to seed.")
        return
        
    print(f"Found {len(existing_files)} JSON files. Seeding ChromaDB...")
    store.reload(existing_files)
    
    print("✅ ChromaDB seeded successfully!")

if __name__ == "__main__":
    seed_database()
