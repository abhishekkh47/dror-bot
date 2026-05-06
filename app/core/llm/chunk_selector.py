import json, re
from app.core.llm.llm import generate_response
from app.utils.logger import logger

def build_chunk_selection_prompt(query, chunks):
    try:
        chunk_descriptions = []

        for idx, (_, chunk) in enumerate(chunks):
            content = chunk["content"]
            if len(content) > 1200:
                content = (
                    content[:700]
                    + "\n...\n"
                    + content[-400:]
                )

            chunk_descriptions.append(
                f"""
                Chunk ID: {chunk['topic']}
                Tags: {', '.join(chunk.get('tags', []))}
                Content: {content}
                """.strip()
            )
            
        joined_chunks = "\n\n".join(chunk_descriptions)
            
        return f"""
        You are a retrieval selection engine.

        Your task:
        Select ONLY chunks containing explicit statements directly answering the user query.

        Selection priority:
        1. Direct root cause
        2. Failure outcome
        3. Cancellation reason
        4. Final state after processing

        Avoid selecting chunks that mainly discuss:
        - lifecycle overviews
        - architecture
        - socket mechanics
        - polling
        - webhooks
        - notifications
        - infrastructure behavior

        DO NOT select chunks focused primarily on:
        - database implementation
        - transaction persistence internals
        - socket delivery
        - webhook behavior
        - polling mechanisms
        - notification systems
        UNLESS the user explicitly asks about those topics.

        Prefer chunks describing:
        - failure cause
        - cancellation reason
        - processing outcome
        - auto-completion result

        Do NOT infer missing information.
        Do NOT summarize.
        Do NOT explain.
        Only select chunks containing direct factual evidence.

        Return ONLY valid JSON.
        Maximum 2 chunk IDs.

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
        
    NOISE_TOPICS = [
        "pending_event",
        "socket",
        "polling",
        "webhook",
        "notification"
    ]
    
    # filtered_chunks = [
    #     (score, chunk)
    #     for score, chunk in scored_chunks
    #     if not any(
    #         noise in chunk["topic"]
    #         for noise in NOISE_TOPICS
    #     )
    # ]

    filtered_chunks = []
    for score, chunk in scored_chunks:
        topic = chunk["topic"].lower()

        noise_penalty = 1.0

        if any(noise in topic for noise in NOISE_TOPICS):
            noise_penalty = 0.35

        adjusted_score = score * noise_penalty

        filtered_chunks.append((adjusted_score, chunk))

    filtered_chunks.sort(key=lambda x: x[0], reverse=True)
    prompt = build_chunk_selection_prompt(query, filtered_chunks)

    try:
        raw_response = generate_response(prompt)
        match = re.search(r'\{.*?\}', raw_response, re.DOTALL)

        if not match:
            return scored_chunks[:2]
        
        parsed = json.loads(match.group())
        # selected_ids = parsed.get("selected_ids", [])
        selected_ids = {
            s.strip().lower()
            for s in parsed.get("selected_ids", [])
        }

        filtered = [
            (score, chunk)
            for score, chunk in filtered_chunks
            if chunk['topic'].lower() in selected_ids
        ]
        filtered.sort(key=lambda x: x[0], reverse=True)

        # fallback
        if not filtered:
            top_score = filtered_chunks[0][0]
            filtered = [
                (s, c)
                for s, c in filtered_chunks
                if s >= max(top_score * 0.75, 0.9)
            ][:2]

        return filtered[:2]
    except Exception as e:
        logger.error(f"Error selecting relevant chunks: {e}")
        return filtered_chunks[:2]