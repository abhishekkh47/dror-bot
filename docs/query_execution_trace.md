# DrorBot: The Live Query Execution Trace

This document provides the exact, live, function-by-function trace of what happens in the code when a user submits a query to the streaming endpoint. It maps exclusively to the active execution path (ignoring dead code or unused files).

---

## The Trace: `POST /query/stream`

When a user types a message and clicks send on the frontend widget, the HTTP request hits the backend. Here is the absolute path of execution, function by function.

### 1. Ingress (`app/api/routes.py`)
1. **`query_stream(request: Request, query_request: QueryRequest)`** is invoked by FastAPI.
2. It immediately calls **`redact_pii(query_request.query)`** (from `app.core.security.pii_redactor`) to strip out credit card numbers or sensitive data.
3. It checks if the user provided a `session_id`. If they didn't, it calls **`session_store.create_qa_session()`** to generate a new UUID and store it in SQLite.
4. It sets up an asynchronous generator called `event_generator()` which wraps the output of the internal orchestrator.
5. It returns a **`StreamingResponse`** back to the client immediately, holding the HTTP connection open with the `text/event-stream` header.

---

### 2. The Orchestrator (`app/core/llm/qa_pipeline.py`)
Inside `event_generator()`, the route calls the pipeline:
1. **`stream_query(query, session_id, session_store)`** is called. 
2. It starts a stopwatch using `time.time()` for telemetry logging later.
3. **Memory:** It checks if a `session_id` was provided and pulls the last 6 messages from the `session_store` to build `history_text`.
4. **Cache Check:** It builds a unique `cache_key` based on the user's `query` and their `history_text`. It asks `redis_client` if this exact context has been answered before.
   - **Cache Hit:** If found, it splits the cached text into words and yields them one-by-one with a tiny `asyncio.sleep` to simulate a real LLM stream back to the browser. The execution stops here.
   - **Cache Miss:** If not found, it hands the query off to a helper function by calling **`_build_qa_prompt(query, session_id, session_store)`**.

#### Inside `_build_qa_prompt(...)`:
1. **Security:** It calls **`validate_request(query)`** (from `app.core.security.request_guard`). If the input is maliciously long or contains prohibited characters, it returns an error immediately.
3. **Query Reformulation:** If there is history, the user might have asked a vague follow-up (e.g., *"How do I test it?"*). It calls **`generate_response(REFORMULATE_PROMPT)`** (from `app.core.llm.llm`) to ask the LLM to rewrite the query into a standalone question (e.g., *"How do I test a webhook signature?"*).
4. **Classification:** It calls **`classify_query_domain(search_query)`** (from `app.core.knowledge.domain_classifier`) which uses a tiny prompt to figure out what domain the question belongs to (e.g., returns the string `"webhooks"`).
5. **Guardrails:** It calls **`enforce_drorpay_scope(domain)`** (from `app.core.knowledge.scope_guard`). If the domain is something like `out_of_scope_cooking`, this function returns False and aborts the pipeline.
6. **Retrieval (The DB Search):** It calls **`store.search(search_query, domain=domain, top_k=6)`** (from `app.core.llm.retriever.py`, which wraps `vector_store.py`). This converts the text into numbers and asks ChromaDB for the 6 most relevant documentation paragraphs.
7. **Filtering:** It runs a simple list comprehension `[chunk for score, chunk in scored_chunks[:3] if score > 0.4]` to throw away any paragraphs with a weak similarity score.
8. **Fallback Logic:** If filtering left 0 chunks, it tries **`store.search(search_query, domain=None, top_k=6)`** (dropping the domain constraint). If it still finds absolutely nothing, it calls **`generate_response(FALLBACK_PROMPT)`** to generate a polite apology and aborts.
9. **Prompt Construction:** It formats the retrieved chunks into a massive `context` string. It then injects the `domain`, `context`, `history_text`, and original `query` into the `QA_SYSTEM_PROMPT` string template.
10. **Return:** It returns the massive assembled prompt back up to `stream_query()`.

---

### 3. Generation and Streaming (`app/core/llm/llm.py`)
Now back inside `stream_query()`, it has the massive prompt string.
1. It calls **`stream_response(prompt)`** (from `app.core.llm.llm`).
2. Inside `stream_response`, the `AsyncOpenAI` client is initialized.
3. It calls **`client.chat.completions.create(..., stream=True)`** sending the prompt to OpenAI.
4. It enters an `async for chunk in response:` loop. 
5. As OpenAI's servers think of words, they arrive over the network. It extracts `chunk.choices[0].delta.content` and **`yields`** that single token string back to `stream_query()`.

---

### 4. Sending the Data to the User (`app/api/routes.py`)
1. Back in `stream_query()`, it catches the yielded token. It appends it to a `full_response` list (so we can save it to the database later), and then **`yields`** the token back to `routes.py`.
2. Back in `routes.py`, `event_generator()` catches the token.
3. It formats the token into a strict Server-Sent Events JSON string: `yield f"data: {{'token': '{token}'}}\n\n"`.
4. FastAPI flushes that string out through the open HTTP socket to the user's browser, where the React widget types it on the screen.
5. This loop repeats hundreds of times until OpenAI is finished talking.

---

### 5. Final Cleanup
Once the OpenAI stream completes and the loops finish:
1. `stream_query()` takes the `full_response` list, joins all the tokens together into the complete answer, and appends it to the `session.history` array.
2. It calls **`session_store.update(session)`** to permanently save the chat to SQLite.
3. It saves the final answer to Redis so future identical queries hit the cache.
4. It calculates the total time taken and calls **`logger.info(...)`** to write a telemetry line to the server logs.
5. Finally, `routes.py` yields the string `"data: [DONE]\n\n"`, which tells the user's browser to close the connection.
