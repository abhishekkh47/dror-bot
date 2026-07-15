"""
LLM provider abstraction layer.

Switch providers at runtime via the PROVIDER environment variable:
  PROVIDER=ollama   → local Ollama (default, free)
  PROVIDER=openai   → OpenAI Chat Completions API
  PROVIDER=gemini   → Google Gemini API

Model selection:
  OLLAMA_MODEL=gemma:2b         (default)
  OPENAI_MODEL=gpt-4o-mini      (default)
  GEMINI_MODEL=gemini-1.5-flash (default)

Public interface:
  generate_response(prompt, json_mode=False) -> str
  stream_response(prompt)                    -> Generator[str]
"""
import os
from typing import Generator
import requests
import dotenv
from app.utils.logger import logger
from openai import OpenAI, AsyncOpenAI

dotenv.load_dotenv()

# ── Provider & model selection ────────────────────────────────────────────────
PROVIDER = os.getenv("PROVIDER", "ollama").lower()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "gemma:2b")

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


# ── Ollama ────────────────────────────────────────────────────────────────────

def _generate_ollama(prompt: str, json_mode: bool = False) -> str:
    payload: dict = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["response"]


def _stream_ollama(prompt: str) -> Generator[str, None, None]:
    with requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
        stream=True,
        timeout=60,
    ) as resp:
        resp.raise_for_status()
        import json as _json
        for line in resp.iter_lines():
            if line:
                chunk = _json.loads(line)
                token = chunk.get("response", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _generate_openai(prompt: str, json_mode: bool = False) -> str:
    client = OpenAI(api_key=OPENAI_API_KEY)
    kwargs: dict = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    completion = client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content


async def _stream_openai(prompt: str):
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    stream = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1024,
        stream=True,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


# ── Gemini ────────────────────────────────────────────────────────────────────

def _generate_gemini(prompt: str, json_mode: bool = False) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def _stream_gemini(prompt: str) -> Generator[str, None, None]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models"
        f"/{GEMINI_MODEL}:streamGenerateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
    }
    import json as _json
    with requests.post(url, json=payload, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                try:
                    data = _json.loads(line.lstrip(b",").lstrip(b"[").rstrip(b"]"))
                    token = data["candidates"][0]["content"]["parts"][0]["text"]
                    if token:
                        yield token
                except (KeyError, ValueError):
                    continue


# ── Registries ────────────────────────────────────────────────────────────────

_GENERATE_PROVIDERS: dict[str, callable] = {
    "ollama": _generate_ollama,
    "openai": _generate_openai,
    "gemini": _generate_gemini,
}

_STREAM_PROVIDERS: dict[str, callable] = {
    "ollama": _stream_ollama,
    "openai": _stream_openai,
    "gemini": _stream_gemini,
}


# ── Public interface ──────────────────────────────────────────────────────────

def generate_response(prompt: str, json_mode: bool = False) -> str:
    """
    Generate a complete response string.
    Set json_mode=True to request structured JSON output (supported by all providers).
    Set PROVIDER env var to switch between: ollama | openai | gemini
    """
    try:
        fn = _GENERATE_PROVIDERS.get(PROVIDER)
        if fn is None:
            raise ValueError(
                f"Unknown PROVIDER: '{PROVIDER}'. "
                f"Supported: {list(_GENERATE_PROVIDERS.keys())}"
            )
        return fn(prompt, json_mode=json_mode)
    except Exception as e:
        logger.error(f"Error generating response [{PROVIDER}]: {e}")
        return f"Error generating response: {e}"


async def stream_response(prompt: str):
    """
    Stream response tokens as an async generator.
    Used by the /query/stream SSE endpoint.
    Set PROVIDER env var to switch between: ollama | openai | gemini
    """
    fn = _STREAM_PROVIDERS.get(PROVIDER)
    if fn is None:
        raise ValueError(
            f"Unknown PROVIDER: '{PROVIDER}'. "
            f"Supported: {list(_STREAM_PROVIDERS.keys())}"
        )
    async for token in fn(prompt):
        yield token
