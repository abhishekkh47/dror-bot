# DrorBot

DrorBot is the official, enterprise-grade AI assistant designed to help third-party developers seamlessly integrate with the DrorPay platform. Powered by a strict Retrieval-Augmented Generation (RAG) architecture, DrorBot dynamically pulls context from internal documentation hosted on Chroma Cloud, ensuring highly accurate, domain-specific answers while strictly rejecting out-of-scope queries.

[🎥 Watch the DrorBot Demo Video](https://drive.google.com/file/d/1Gw4IK3zGHPabBuev8KDcoR6lKL4uBc9D/view?usp=sharing)

---

## 🚀 Setup Instructions

### Prerequisites
- Python 3.12 or higher
- Redis (optional, for session storage caching)
- API Keys for your preferred LLM provider (OpenAI, Ollama, or Gemini)
- API Keys for ChromaDB

### 1. Clone & Environment Setup
Clone the repository and create a virtual environment:
```bash
python -m venv .drorenv
source .drorenv/bin/activate
```

### 2. Install Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory and configure it with your credentials:
```ini
PORT=8000
PROVIDER=openai # Choose: ollama | openai | gemini

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Vector Database (Chroma)
CHROMA_DB_API_KEY=your_chroma_key
CHROMA_DB_TENANT=your_tenant_id
CHROMA_DB_NAME=dror-bot

# Redis (Set to false if running in-memory locally)
REDIS_ENABLED=false
```

### 4. Running the Server
Start the FastAPI server using Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API will be available at `http://localhost:8000`. You can view the interactive Swagger documentation at `http://localhost:8000/docs`.

---

## 🚀 API Endpoints

The DrorBot API provides a clean, conversational interface for developers to retrieve answers about authentication, payments, webhooks, and general platform integrations.

### 🤖 For Third-Party Developers (The AI Assistant)

These are the core endpoints that your developers (or your frontend UI) will use to ask questions and interact with the bot:

#### 1. `POST /session/start` (Initialize Session)
Generates a persistent session ID on the backend and initializes an empty conversation history in the SQLite database.

**Payload:** None
**Response:**
```json
{
  "session_id": "a1b2c3d4-..."
}
```

#### 2. `POST /query` (Standard JSON Response)
Best for backend-to-backend integrations or simple UI requests where you want the full answer returned at once.

**Payload:**
```json
{
  "query": "How do I verify a webhook signature?",
  "session_id": "user_123" 
}
```
*Note: `session_id` is an arbitrary string provided by the client. The server uses it to remember conversation history.*

**Response:**
A JSON object containing the complete `answer`, the detected `domain`, a `confidence` score, and the exact `citations` (sources) it used.

#### 3. `POST /query/stream` (Streaming Response)
Best for user-facing chat interfaces. It uses Server-Sent Events (SSE) to stream the text back one token at a time, providing a fast, ChatGPT-like typing experience.

**Payload:**
```json
{
  "query": "What are the required headers for creating a payment intent?",
  "session_id": "user_123"
}
```
*Note: The response will stream back token by token and end with a `[DONE]` event.*

#### 4. `POST /feedback`
Allows developers to rate the bot's answers (e.g., thumbs up / thumbs down) so you can monitor quality and make continuous improvements.

**Payload:**
```json
{
  "session_id": "user_123",
  "rating": "positive",
  "comments": "Very helpful!"
}
```

---

### ⚙️ For Internal Administration

#### 5. `POST /admin/sync-docs`
This is a private webhook endpoint that your internal backend scripts (e.g., `send_docs_to_bot.py`) call to push fresh markdown documentation into the Chroma database.

**Payload:**
```json
{
  "files": [
    {
      "filename": "webhooks.md",
      "content": "# Webhooks\n..."
    }
  ]
}
```
