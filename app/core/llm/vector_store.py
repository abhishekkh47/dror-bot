import json
import numpy as np
from app.core.llm.embedding import get_embedding

class VectorStore:
    def __init__(self, path: str):
        with open(path, "r") as f:
            """
            json.load() → reads from file object
            json.loads() → parses string
            """
            # self.chunks = json.loads(f)
            self.chunks = json.load(f)
        
        self.vectors = []
        self._build_index()

    def _build_index(self):
        for chunk in self.chunks:
            text_to_embed = f"""
            Topic: {chunk.get('topic', '')}
            Type: {chunk.get('type', '')}
            Tage: {', '.join(chunk.get('tags', []))}
            Content: {chunk.get('content', '')}
            """
            # embedding = get_embedding(chunk["content"])
            # improve embedding by adding more context
            embedding = get_embedding(text_to_embed)

            self.vectors.append({
                "embedding": np.array(embedding),
                "chunk": chunk
            })

    def cosine_similarity(self, a, b):
        return np.dot(a,b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    # More candidates (top_k) → better chance correct chunk appears
    def search(self, query: str, top_k=8):
        query_vec = np.array(get_embedding(query))

        scored = []
        for item in self.vectors:
            score = self.cosine_similarity(query_vec, item["embedding"])

            importance_boost = {
                "high": 1.2,
                "medium": 1.0,
                "low": 0.8
            }.get(item["chunk"].get("importance", "medium"), 1.0)

            type_boost = 1.1 if item["chunk"]["type"] == "explanation" else 1.0

            # final_score = score * importance_boost * type_boost
            # Update scoring
            query_lower = query.lower()
            content_lower = item["chunk"]["content"].lower()
            keyword_bonus = 0.0
            if any(word in content_lower for word in query_lower.split()):
                keyword_bonus = 0.1
            final_score = (score + keyword_bonus) * importance_boost * type_boost

            scored.append((final_score, item["chunk"]))

            for s, c in scored[:5]:
                print(f"SCORE: {s:.4f} | {c['id']}")

        scored.sort(key=lambda x: x[0], reverse=True)

        return [chunk for _, chunk in scored[:top_k]]