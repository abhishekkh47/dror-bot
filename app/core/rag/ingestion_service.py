import json
import os
from pathlib import Path
from langchain_text_splitters import MarkdownHeaderTextSplitter
from app.core.llm.llm import generate_response

METADATA_PROMPT = """Analyze the following documentation chunk and generate JSON metadata.
Extract:
1. "capability": The main API/feature this discusses (e.g., "authentication", "webhooks", "payment_intents").
2. "lifecycle_stage": One of [initialization, processing, confirmation, dispute, general].
3. "tags": A list of 2-4 lowercase keyword tags relevant to the content.
4. "type": One of [explanation, code, troubleshooting, reference].

Respond ONLY with valid JSON.
Example: {{"capability": "webhooks", "lifecycle_stage": "confirmation", "tags": ["signature", "verification"], "type": "code"}}

CHUNK:
{chunk}
"""

def process_markdown_files(files_data: list[dict]):
    """
    files_data is a list of dictionaries:
    [
        {"filename": "DRORPAY_COMPLETE_DOCUMENTATION.md", "content": "# DrorPay..."}
    ]
    """
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    
    processed_chunks = []
    
    for file_data in files_data:
        filename = file_data.get("filename", "unknown.md")
        content = file_data.get("content", "")
        
        md_header_splits = markdown_splitter.split_text(content)
        
        for doc in md_header_splits:
            chunk_content = doc.page_content
            # Combine headers for topic
            topic_parts = []
            for h in ["Header 1", "Header 2", "Header 3"]:
                if h in doc.metadata:
                    topic_parts.append(doc.metadata[h])
            
            topic = filename + " > " + " > ".join(topic_parts) if topic_parts else filename
            
            # Generate metadata
            prompt = METADATA_PROMPT.format(chunk=chunk_content[:1500])  # limit size for prompt
            try:
                response = generate_response(prompt).strip()
                # Clean markdown block if LLM added it
                if response.startswith("```json"):
                    response = response[7:-3]
                
                meta = json.loads(response)
            except Exception as e:
                meta = {
                    "capability": "general",
                    "lifecycle_stage": "general",
                    "tags": [],
                    "type": "explanation"
                }
                
            chunk_obj = {
                "topic": topic,
                "type": meta.get("type", "explanation"),
                "tags": meta.get("tags", []),
                "metadata": {
                    "capability": meta.get("capability", "general"),
                    "lifecycle_stage": meta.get("lifecycle_stage", "general"),
                    "source": filename
                },
                "content": chunk_content
            }
            processed_chunks.append(chunk_obj)
            
    # Save to disk
    output_path = Path("app/data/knowledge_base/dynamic_ingestion.json")
    os.makedirs(output_path.parent, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(processed_chunks, f, indent=2)
        
    return processed_chunks
