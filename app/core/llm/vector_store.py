import json
import numpy as np
import os
import chromadb
from app.core.llm.embedding import get_embedding
from app.utils.constants import CONTEXT_TAGS, CRITICAL_TAGS, INTENT_DEFINITIONS, TAG_PRIORITY
import re
import hashlib
from dotenv import load_dotenv

load_dotenv()

class VectorStore:
    def __init__(self, path: str | list[str], db_path: str = "app/data/chroma_db"):
        self.db_path = db_path
        
        # Check for Chroma Cloud credentials
        tenant = os.getenv("CHROMA_DB_TENANT")
        database = os.getenv("CHROMA_DB_NAME")
        api_key = os.getenv("CHROMA_DB_API_KEY")
        
        if tenant and database and api_key:
            print(f"Connecting to Chroma Cloud (Tenant: {tenant}, DB: {database})")
            self.chroma_client = chromadb.CloudClient(
                tenant=tenant,
                database=database,
                api_key=api_key
            )
        else:
            print("Connecting to local ChromaDB SQLite")
            os.makedirs(db_path, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=db_path)
            
        self.collection = self.chroma_client.get_or_create_collection(
            name="drorpay_docs",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.topic_embeddings = {}
        self.reload(path)

    def reload(self, path: str | list[str]):
        if not path:
            return
        if isinstance(path, str):
            path = [path]
        
        chunks = []
        for p in path:
            if os.path.exists(p):
                with open(p, "r") as f:
                    chunks.extend(json.load(f))
        
        self._build_index(chunks)
        self.build_topic_index(chunks)

    def _generate_id(self, chunk):
        # Unique ID based on topic and content hash
        content = chunk.get('content', '')
        topic = chunk.get('topic', 'unknown')
        return hashlib.md5((topic + content).encode('utf-8')).hexdigest()

    def _build_index(self, chunks):
        ids = []
        embeddings = []
        metadatas = []
        documents = []

        # We will retrieve all existing ids to avoid re-embedding if possible
        existing = self.collection.get(include=[])
        existing_ids = set(existing["ids"]) if existing["ids"] else set()

        for chunk in chunks:
            chunk_id = self._generate_id(chunk)
            
            # Prepare metadata (must be str, int, float or bool)
            meta = {
                "topic": chunk.get("topic", ""),
                "type": chunk.get("type", ""),
                "importance": chunk.get("importance", "medium"),
                "tags": ",".join(chunk.get("tags", []))
            }

            if chunk_id not in existing_ids:
                text_to_embed = f"""
                Topic: {chunk.get('topic', '')}
                Type: {chunk.get('type', '')}
                Tags: {', '.join(chunk.get('tags', []))}
                Content: {chunk.get('content', '')}
                """
                embedding = get_embedding(text_to_embed)
                
                ids.append(chunk_id)
                embeddings.append(embedding)
                metadatas.append(meta)
                documents.append(chunk.get("content", ""))

        if ids:
            # Upsert in batches of 100
            for i in range(0, len(ids), 100):
                self.collection.upsert(
                    ids=ids[i:i+100],
                    embeddings=embeddings[i:i+100],
                    metadatas=metadatas[i:i+100],
                    documents=documents[i:i+100]
                )

    def cosine_similarity(self, a, b):
        return np.dot(a,b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def normalize_token(self,token: str):
        mapping = {
            "fails": "failure",
            "failed": "failure",
            "error": "failure",
            "errors": "failure",
            "success": "success",
            "succeeded": "success"
        }
        return mapping.get(token, token)

    def detect_intent_semantic(self, query: str):
        try:
            query_vec = np.array(get_embedding(query))
            best_intent = None
            best_score = -1
            
            for intent, examples in INTENT_DEFINITIONS.items():
                for example in examples:
                    example_vec = np.array(get_embedding(example))
                    score = self.cosine_similarity(query_vec, example_vec)
                    
                    if score > best_score:
                        best_score = score
                        best_intent = intent
                    
            if best_score > 0.75:
                return best_intent
            return None
        except Exception as e:
            print(f"Error detecting intent: {e}")
            return None
    
    def search(self, query: str, step=None, top_k=8):
        query_vec = get_embedding(query)
        
        # 1. RETRIEVE top 20 candidates from ChromaDB
        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=20,
            include=["embeddings", "metadatas", "documents", "distances"]
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        # Convert Chroma results back into our chunk format for re-ranking
        candidates = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            embedding = results["embeddings"][0][i]
            
            chunk = {
                "topic": meta.get("topic", ""),
                "type": meta.get("type", ""),
                "importance": meta.get("importance", "medium"),
                "tags": meta.get("tags", "").split(",") if meta.get("tags") else [],
                "content": results["documents"][0][i]
            }
            candidates.append({
                "embedding": np.array(embedding),
                "chunk": chunk
            })

        query_vec_np = np.array(query_vec)
        tokens = re.findall(r'\b\w+\b', query.lower())
        query_tokens = set(self.normalize_token(token) for token in tokens)

        step_domain = getattr(step, "domain", None) if step else None
        intent = self.detect_intent_semantic(query)

        if step and not step_domain:
            raise ValueError(f"Step '{step.id}' missing domain")

        # 2. RE-RANK using custom logic
        scored = []
        for item in candidates:
            chunk = item["chunk"]
            chunk_topic = chunk.get("topic", "")

            similarity_score = self.cosine_similarity(query_vec_np, item["embedding"])

            if step_domain:
                allowed = step_domain if isinstance(step_domain, list) else [step_domain]                
                if not any(chunk_topic.startswith(d) for d in allowed):
                    continue

            chunk_tags = set(self.normalize_token(tag) for tag in chunk.get("tags", []))

            intent_boost = 1.0
            if intent:
                intent_boost = 1.5 if intent in chunk_tags else 0.7

            importance_boost = {
                "high": 1.3,
                "medium": 1.0,
                "low": 0.7
            }.get(chunk.get("importance", "medium"), 1.0)

            type_boost = 1.1 if chunk.get("type") == "explanation" else 1.0
            
            tag_score = 0.0
            for tag in chunk_tags:
                if tag in query_tokens:
                    if tag in CRITICAL_TAGS:
                        tag_score += CRITICAL_TAGS[tag]
                    else:
                        tag_score += CONTEXT_TAGS.get(tag, 1.0)
            
            tag_boost = 1 + min(1.5, tag_score / 2)

            content_tokens = set(chunk.get("content", "").lower().split())
            keyword_overlap = len(query_tokens & content_tokens)
            keyword_boost = 1 + min(0.2, 0.05 * keyword_overlap)

            critical_match = any(tag in CRITICAL_TAGS for tag in chunk_tags if tag in query_tokens)
            critical_boost = 1.2 if critical_match else 1.0
            
            tag_weight = 2.5
            intent_weight = 2.0

            base_score = similarity_score * importance_boost * type_boost * critical_boost
            tag_component = tag_boost * tag_weight
            intent_component = intent_boost * intent_weight

            final_score = (
                base_score * 0.6 +
                tag_component * 0.25 +
                intent_component * 0.15
            ) * keyword_boost

            scored.append((final_score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        print("\n--- RETRIEVAL DEBUG ---")
        for s, c in scored[:5]:
            print(f"{s:.4f} | {c['topic']} | {c.get('tags', [])}")

        return scored[:top_k]
    
    def build_topic_index(self, chunks):
        self.topic_embeddings = {}
        topics = set(chunk["topic"] for chunk in chunks)

        for topic in topics:
            self.topic_embeddings[topic] = np.array(get_embedding(topic))