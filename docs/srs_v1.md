# Software Requirements Specification (SRS)

## Drorpay Integration AI Assistant

---

# 1. System Overview

## 1.1 Objective

Build an AI-powered assistant to help external developers integrate Drorpay by:

* Providing precise API-level answers (QA Mode)
* Guiding developers through integration flows (Flow Mode)
* Diagnosing and resolving issues (Debug Mode)

The system must:

* Use only safe, curated data
* Prevent exposure of internal system details
* Avoid hallucinations via controlled reasoning

---

## 1.2 Problem Statement

Developers integrating Drorpay face:

* Lack of clarity in API usage
* Difficulty understanding full integration flow
* Trouble debugging transaction failures

Traditional documentation is insufficient for:

* contextual guidance
* real-time debugging
* step-by-step execution

---

## 1.3 System Scope

### Included

* API documentation assistance
* Integration flow guidance
* Error diagnosis and resolution
* Multi-turn interaction (stateful)

### Excluded

* Internal system exposure (DB, services)
* Admin/internal APIs
* Direct execution of transactions

---

# 2. User Intents

The system supports the following intents:

```ts
type Intent =
  | "API_LOOKUP"
  | "INTEGRATION_FLOW"
  | "DEBUG_ISSUE"
```

---

# 3. Interaction Modes

## 3.1 QA Mode (Stateless)

**Trigger:** API_LOOKUP

**Purpose:**
Provide precise API-level answers.

**Characteristics:**

* No follow-up questions
* No flow continuation
* Strictly context-based answers

---

## 3.2 Flow Mode (Stateful)

**Trigger:** INTEGRATION_FLOW

**Purpose:**
Guide user step-by-step through integration.

**Characteristics:**

* Maintains session state
* Controlled transitions
* Can pause/resume

---

## 3.3 Debug Mode (Hybrid)

**Trigger:** DEBUG_ISSUE

**Purpose:**
Diagnose issues using structured error intelligence.

**Characteristics:**

* Uses error mapping + embeddings
* Returns structured diagnosis
* Avoids guessing

---

# 4. Core System Architecture

```text
User Query
   ↓
Intent Classifier
   ↓
Mode Router
   ↓
-----------------------------------
| QA → Retriever → LLM           |
| FLOW → Flow Engine → LLM       |
| DEBUG → Error Engine → LLM     |
-----------------------------------
   ↓
Output Validator
   ↓
Response
```

---

# 5. Knowledge Base Design

## 5.1 Allowed Data Sources

* Public API documentation
* Integration guides
* SDK usage
* Sample requests/responses
* Webhook documentation

---

## 5.2 Restricted Data

* Internal APIs
* Database schema
* Admin services
* Secrets / tokens

---

## 5.3 Document Schema

```json
{
  "id": "string",
  "topic": "payment | auth | webhook",
  "type": "public_api | guide",
  "step": "optional_flow_step",
  "content": "text",
  "metadata": {
    "safe": true
  }
}
```

---

# 6. Retrieval System (RAG)

## 6.1 Retrieval Inputs

```json
{
  "query": "string",
  "filters": {
    "topic": "string",
    "type": "string"
  }
}
```

---

## 6.2 Retrieval Rules

* Only safe documents
* Metadata filtering required
* Top-K similarity search

---

## 6.3 Embeddings

* Used for semantic search
* Used in debug fallback (error matching)

---

# 7. Flow Engine

## 7.1 Flow Definition (Reference: Payment Execution)

```json
{
  "flow_id": "payment_execution",
  "steps": [
    "create_intent",
    "handle_response",
    "listen_updates",
    "handle_success",
    "handle_failure",
    "refund_optional"
  ]
}
```

---

## 7.2 Step Types

```ts
type StepType =
  | "ACTION"
  | "INFO"
  | "DECISION"
  | "OPTIONAL"
```

---

## 7.3 State Model

```json
{
  "session_id": "string",
  "flow_id": "string",
  "current_step": "string",
  "history": [],
  "collected_data": {}
}
```

---

## 7.4 Behavior

* Flow engine controls progression
* LLM only explains steps
* State persisted per session

---

# 8. Error Intelligence System

## 8.1 Purpose

Provide deterministic debugging using structured error definitions.

---

## 8.2 Components

* Error taxonomy (`errors.json`)
* Direct mapping engine
* Embedding-based fallback
* Confidence scoring

---

## 8.3 Resolution Pipeline

```text
User Query
   ↓
Check backend error
   ↓ yes → direct match
   ↓ no
Embedding match
   ↓
Rank candidates
   ↓
LLM explanation
```

---

## 8.4 Output Format

```json
{
  "issue": "string",
  "possible_causes": [],
  "how_to_verify": [],
  "resolution": []
}
```

---

## 8.5 Rules

* No unknown error inference
* Multiple candidates allowed
* Low confidence → ask for clarification

---

# 9. Guardrails & Security

## 9.1 Input Guard

* Detect malicious prompts
* Block “internal system” queries

---

## 9.2 Context Firewall

* Strip sensitive data
* Allow only safe schema fields

---

## 9.3 Output Validator

Reject response if:

* Contains internal endpoints
* Mentions secrets
* Hallucinates APIs

---

# 10. Prompt Design

## 10.1 QA Prompt

```text
- Answer only from context
- Do not infer
- Return structured response
```

---

## 10.2 Flow Prompt

```text
- Explain current step only
- Do not jump ahead
- Include API examples
```

---

## 10.3 Debug Prompt

```text
- Use only known error data
- Do not guess
- Provide causes + resolution
```

---

# 11. API Design

## 11.1 POST /query

### Request

```json
{
  "query": "string",
  "session_id": "optional"
}
```

---

### Response

```json
{
  "mode": "QA | FLOW | DEBUG",
  "answer": "string",
  "step": "optional",
  "next_actions": []
}
```

---

## 11.2 POST /flow/answer

```json
{
  "session_id": "string",
  "answer": "string"
}
```

---

# 12. Evaluation Strategy

## 12.1 Test Queries

* “How to integrate payment?”
* “Login API params”
* “Payment failed”
* “Webhook not working”

---

## 12.2 Metrics

* Accuracy
* Hallucination rate
* Flow completion success
* Debug correctness

---

# 13. Development Phases

## Phase 1

* QA Mode
* Basic RAG

## Phase 2

* Flow Engine
* State Management

## Phase 3

* Debug Mode
* Error Intelligence

## Phase 4

* Guardrails
* Evaluation & tuning

---

# 14. Tech Stack

* Backend: Node.js
* LLM: Gemma (Ollama)
* Embeddings: local/API
* Vector DB: Chroma / SQLite
* Storage: JSON + DB

---

# 15. Constraints & Assumptions

* LLM may hallucinate → must be controlled
* All data must be curated
* Performance depends on local model limits

---

# 16. Success Criteria

System is successful if:

* Developers can integrate without external help
* Debugging accuracy is high
* No internal data leakage occurs
* Responses are consistent and structured

---

# END OF DOCUMENT
