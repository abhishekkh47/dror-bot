# White-Labeling Guide

This document explains how to repurpose the RAG engine for any other business domain (e.g., Hotel Bookings, E-commerce, Internal HR Support) by detaching it from the hardcoded DrorPay context.

The core retrieval and streaming architecture is highly reusable, but the bot's "personality" and guardrails need to be abstracted.

## 1. Environment Configuration (`.env`)
You should move the hardcoded identity variables to your environment configuration to make deployments flexible across different businesses.

Add variables like the following to your `.env` file:
```ini
BUSINESS_NAME="Grand Hotel"
BUSINESS_CONTEXT="a luxury hotel booking system"
BOT_PERSONA="a helpful concierge"
```

## 2. Dynamic Prompts (`app/core/llm/prompts.py`)
Currently, the system prompts heavily reference "DrorPay". You need to refactor these to use the `.env` variables dynamically.

**System Prompt Example:**
```python
import os

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Our Company")
BOT_PERSONA = os.getenv("BOT_PERSONA", "a helpful assistant")

QA_SYSTEM_PROMPT = f"""
You are {BOT_PERSONA} for {BUSINESS_NAME}.
Your primary goal is to assist users based strictly on the provided context.
...
"""
```

**Guardrail & Fallback Prompts:**
Ensure `FALLBACK_PROMPT` and `ENFORCE_SCOPE_PROMPT` dynamically reference the `BUSINESS_CONTEXT` to effectively reject out-of-scope queries (e.g., a hotel bot should reject software programming questions).

## 3. Dynamic Domain Routing (`app/core/llm/qa_pipeline.py`)
The bot currently categorizes queries into specific predefined domains like `authentication` or `transactions`. 

**Steps to adapt:**
1. Update `classify_query_domain(query)` to either dynamically extract the domain using the LLM without a predefined list, **OR** load an allowed list of domains from a configuration file (e.g., `["booking", "amenities", "cancellations"]`).
2. Ensure the routing prompt passes these new domains so the LLM categorizes user queries correctly.

## 4. Scope Guardrails Modification
In the QA pipeline, there is a function named `enforce_drorpay_scope()` which explicitly blocks non-DrorPay queries.
1. Rename this to `enforce_business_scope()`.
2. Update its internal logic to pass the `BUSINESS_CONTEXT` from your `.env` into the LLM evaluator, so it knows exactly what topics are authorized.

## 5. ChromaDB Knowledge Base Reseeding
Finally, the existing ChromaDB contains DrorPay documentation.
1. Create a fresh ChromaDB collection by updating `CHROMA_DB_NAME` in the `.env` file.
2. Upload your new markdown documentation using the `POST /admin/sync-docs` endpoint.
3. Ensure your new documents are structured with appropriate metadata topics that match your new domain routing configuration.
