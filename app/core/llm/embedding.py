"""
Embedding provider abstraction layer.

Follows the same PROVIDER env variable as llm.py:
  PROVIDER=ollama  → nomic-embed-text via local Ollama
  PROVIDER=openai  → text-embedding-3-small via OpenAI API
  PROVIDER=gemini  → embedding-001 via Google Generative Language API

Model selection:
  OLLAMA_EMBEDDING_MODEL=nomic-embed-text       (default)
  OPENAI_EMBEDDING_MODEL=text-embedding-3-small  (default)
  GEMINI_EMBEDDING_MODEL=embedding-001           (default)
"""
import os
import requests
import dotenv

dotenv.load_dotenv()

PROVIDER = os.getenv("PROVIDER", "ollama").lower()

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL         = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL  = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY          = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL  = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY          = os.getenv("GEMINI_API_KEY", "")
GEMINI_EMBEDDING_MODEL  = os.getenv("GEMINI_EMBEDDING_MODEL", "embedding-001")


# ── Provider implementations ──────────────────────────────────────────────────

def _embed_ollama(text: str) -> list[float]:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": OLLAMA_EMBEDDING_MODEL, "prompt": text},
    )
    response.raise_for_status()
    return response.json()["embedding"]


def _embed_openai(text: str) -> list[float]:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def _embed_gemini(text: str) -> list[float]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{GEMINI_EMBEDDING_MODEL}:embedContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "model": f"models/{GEMINI_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text}]},
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()["embedding"]["values"]


# ── Registry ──────────────────────────────────────────────────────────────────
_PROVIDERS: dict[str, callable] = {
    "ollama": _embed_ollama,
    "openai": _embed_openai,
    "gemini": _embed_gemini,
}


# ── Public interface ──────────────────────────────────────────────────────────
def get_embedding(text: str) -> list[float]:
    """
    Return an embedding vector for the given text using the configured provider.
    Set PROVIDER env var to switch between: ollama | openai | gemini
    """
    fn = _PROVIDERS.get(PROVIDER)
    if fn is None:
        raise ValueError(
            f"Unknown PROVIDER: '{PROVIDER}'. "
            f"Supported values: {list(_PROVIDERS.keys())}"
        )
    return fn(text)
