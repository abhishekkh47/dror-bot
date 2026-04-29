import requests, os
import dotenv
dotenv.load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
MODEL = "gemma:2b"

def generate_response(prompt: str) -> str:
    response = requests.post(
        OLLAMA_GENERATE_URL,
        json = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }
    )
    response.raise_for_status()
    return response.json()["response"]