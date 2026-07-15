import os
import sys

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.rag.ingestion_service import process_markdown_files
from app.core.llm.retriever import store, KNOWLEDGE_FILES

def sync_markdown():
    print("Reading markdown file...")
    md_path = "../drorpay-backend/PAYMENT_GATEWAY_INTEGRATION.md"
    
    with open(md_path, "r") as f:
        content = f.read()
        
    print("Processing markdown...")
    processed_chunks = process_markdown_files([{"filename": "PAYMENT_GATEWAY_INTEGRATION.md", "content": content}])
    print(f"Generated {len(processed_chunks)} chunks.")
    
    print("Seeding Vector DB...")
    if "app/data/knowledge_base/dynamic_ingestion.json" not in KNOWLEDGE_FILES:
        KNOWLEDGE_FILES.append("app/data/knowledge_base/dynamic_ingestion.json")
    
    existing_files = [f for f in KNOWLEDGE_FILES if os.path.exists(f)]
    store.reload(existing_files)
    print("Done!")

if __name__ == "__main__":
    sync_markdown()
