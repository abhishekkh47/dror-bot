# DrorBot

DrorBot is the official, enterprise-grade AI assistant designed to help third-party developers seamlessly integrate with the DrorPay platform. Powered by a strict Retrieval-Augmented Generation (RAG) architecture, DrorBot dynamically pulls context from internal documentation hosted on Chroma Cloud, ensuring highly accurate, domain-specific answers while strictly rejecting out-of-scope queries.

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
*Note: `session_id` is an arbitrary string provided by the client (e.g., a UUID generated in the frontend or the developer's user ID). The server uses it to remember conversation history. If the session doesn't exist, the server will automatically create it.*

**Response:**
A JSON object containing the complete `answer`, the detected `domain`, a `confidence` score, and the exact `citations` (sources) it used.

#### 2. `POST /query/stream` (Streaming Response)
Best for user-facing chat interfaces. It uses Server-Sent Events (SSE) to stream the text back one token at a time, providing a fast, ChatGPT-like typing experience.

**Payload:**
```json
{
  "query": "What are the required headers for creating a payment intent?",
  "session_id": "user_123"
}
```
*Note: The response will stream back token by token and end with a `[DONE]` event.*

#### 3. `POST /feedback`
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

#### 4. `POST /admin/sync-docs`
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
