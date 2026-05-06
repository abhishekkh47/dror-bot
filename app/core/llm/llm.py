import requests, os
import dotenv
from app.utils.logger import logger
dotenv.load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
MODEL = "gemma:2b"

def generate_response(prompt: str) -> str:
    try:
        response = requests.post(
            OLLAMA_GENERATE_URL,
            json = {
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return f"Error generating response: {e}"