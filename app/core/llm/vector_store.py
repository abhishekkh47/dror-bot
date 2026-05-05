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
        self.build_topic_index()

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
    def search(self, query: str, step=None, top_k=8):
        query_vec = np.array(get_embedding(query))
        query_tokens = set(query.lower().split())

        # step_prefix = None
        # if step and step.rag_topic:
        #     step_prefix = step.rag_topic.split("_")[0]
        
        step_domain = None
        step_domain = getattr(step, "domain", None) if step else None

        if step and not step_domain:
            raise ValueError(f"Step '{step.id}' missing domain")

        scored = []
        for item in self.vectors:
            chunk = item["chunk"]
            chunk_topic = chunk.get("topic", "")

            similarity_score = self.cosine_similarity(query_vec, item["embedding"])

            """
            Hard cutoff (cross-domain suppression)
            Discard weak cross-domain matches to prevent:
            - random cross-domain leakage
            - noisy fallback behavior
            """
            # if step_prefix and not chunk_topic.startswith(step_prefix):
            #     continue
            if step_domain:
                allowed = step_domain if isinstance(step_domain, list) else [step_domain]                
                if not any(chunk_topic.startswith(d) for d in allowed):
                    continue

            # Importance Boost
            importance_boost = {
                "high": 1.3,
                "medium": 1.0,
                "low": 0.7
            }.get(chunk.get("importance", "medium"), 1.0)

            # Type Boost
            type_boost = 1.1 if chunk.get("type") == "explanation" else 1.0

            # Tag overlap boost (strong signal)
            chunk_tags = set(chunk.get("tags", []))
            tag_overlap = len(query_tokens & chunk_tags)
            tag_boost = 1 + (0.15 * tag_overlap)

            # Keyword boost (secondary, minor signal)
            content_tokens = set(chunk.get("content", "").lower().split())
            keyword_overlap = len(query_tokens & content_tokens)
            keyword_boost = 1 + (0.05 * keyword_overlap)

            # Topic boost (contextual relevance) (secondary, minor signal)
            # if step_prefix:
            #     topic_boost = 1.5 if chunk_topic.startswith(step_prefix) else 0.2
            # else:
            #     topic_boost = 1.0
            
            """
            Apply topic boost early to avoid rescuing wrong-domain chunks by tags/keywords
            This ensures:
            - wrong-domain chunks drop early
            - don't get rescued by tags/keywords later
            """
            # adjusted_similarity = similarity_score * topic_boost
            
            base_score = similarity_score * importance_boost * type_boost
            signal_boost = (tag_boost + keyword_boost) / 2
            final_score = base_score * signal_boost

            # Update scoring
            scored.append((final_score, chunk))


        # After scoring everything, sort by score descending and return top_k
        scored.sort(key=lambda x: x[0], reverse=True)

        print("\n--- RETRIEVAL DEBUG ---")
        for s, c in scored[:5]:
            # print(f"SCORE: {s:.4f} | {c['id']}")
            print(f"{s:.4f} | {c['topic']} | {c.get('tags', [])}")

        return scored[:top_k]
    
    # Pre-compute topic embeddings
    def build_topic_index(self):
        self.topic_embeddings = {}
        topics = set(chunk["topic"] for chunk in self.chunks)

        for topic in topics:
            self.topic_embeddings[topic] = np.array(get_embedding(topic))