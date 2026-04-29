import requests
import os
import dotenv
dotenv.load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_EMBEDDING_URL = f"{OLLAMA_BASE_URL}/api/embeddings"
MODEL = "nomic-embed-text"

def get_embedding(text: str) -> list[float]:
    response = requests.post(
        OLLAMA_EMBEDDING_URL,
        json = {
            "model": MODEL,
            "prompt": text
        }
    )
    response.raise_for_status()
    return response.json()["embedding"]