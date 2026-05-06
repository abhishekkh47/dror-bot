import json
from app.core.llm.llm import generate_response
from app.utils.logger import logger

def build_chunk_selection_prompt(query, chunks):
    try:
        chunk_descriptions = []

        for idx, (_, chunk) in enumerate(chunks):
            chunk_descriptions.append(
                f"""
                Chunk ID: {chunk['topic']}
                Tags: {', '.join(chunk.get('tags', []))}
                Content: 
                {chunk['content'][:700]}
                """.strip()
            )
            
            joined_chunks = "\n\n".join(chunk_descriptions)
            
            return f"""
            You are a retrieval filter for a RAG system.

            Your job: 
            Select only the chunks that directly answer the user's query.

            STRICT RULES:
            - Return only relevant chunk IDs
            - Maximum of 2 chunks IDs
            - Ignore chunks containing:
                - Sockets
                - Webhooks
                - Polling
                - Notifications
                unless explicitly asked.
            - Prefer chunks explaining:
                - Root cause
                - Failure reason
                - Outcome
            - Do not explain anything
            - Do not summarize
            - Output ONLY valid JSON

            User Query:
            {query}

            Chunks:
            {joined_chunks}

            Output ONLY valid JSON with the following format:
            {{
                "selected_ids": ["chunk_id_1", "chunk_id_2"]
            }}
            """.strip()
    except Exception as e:
        print(f"Error building chunk selection prompt: {e}")
        return (f"Error building chunk selection prompt: {e}")

def select_relevant_chunks(query, scored_chunks):
    if not scored_chunks:
        return []
    
    prompt = build_chunk_selection_prompt(query, scored_chunks)

    try:
        raw_response = generate_response(prompt)
        parsed = json.loads(raw_response)
        selected_ids = parsed.get("selected_ids", [])

        filtered = [
            (score, chunk)
            for score, chunk in scored_chunks
            if chunk['topic'] in selected_ids
        ]

        # fallback
        if not filtered:
            filtered = scored_chunks[:2]

        return filtered[:2]
    except Exception as e:
        logger.error(f"Error selecting relevant chunks: {e}")
        return scored_chunks[:2]