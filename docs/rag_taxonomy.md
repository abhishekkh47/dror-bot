# Canonical RAG Knowledge Taxonomy

## 1. business_domain

Top-level product/business area.

Examples:
- payments
- refunds
- disputes
- wallets
- kyc

Purpose:
High-level retrieval isolation.

---

## 2. capability

Specific workflow/API capability.

Examples:
- create_intent
- payment_status
- auto_completion
- refund_processing

Purpose:
Primary retrieval scope.

---

## 3. lifecycle_stage

Operational phase of the workflow.

Examples:
- authentication
- validation
- transaction_creation
- auto_completion
- settlement
- cancellation
- completion
- reconciliation

Purpose:
Lifecycle-aware retrieval and chronology grounding.

---

## 4. operational_state

State represented by the chunk.

Examples:
- pending
- completed
- failed
- cancelled

Purpose:
Failure/cancellation reasoning.

---

## 5. knowledge_type

Semantic role of the knowledge.

Examples:
- api_spec
- operational_behavior
- business_rule
- troubleshooting
- edge_case
- integration_guidance
- transport_behavior

Purpose:
Control retrieval relevance.

---

## 6. artifact_type

Structural format of the information.

Examples:
- flow
- payload
- schema
- rules
- explanation
- event

Purpose:
Formatting / parsing / retrieval weighting.

---

## 7. mechanism

Transport or communication mechanism.

Examples:
- webhook
- socket
- polling
- http
- none

Purpose:
Mechanism-aware suppression and filtering.

---

## 8. visibility

Audience visibility level.

Examples:
- public_integrator
- internal_only

Purpose:
Prevent accidental leakage.

---

## 9. importance

Retrieval priority weighting.

Examples:
- low
- medium
- high
- critical

Purpose:
Ranking boost logic.


# Retrieval Priority Rules

## Highest Priority

- Matching capability
- Matching lifecycle_stage
- Matching operational_state

## Medium Priority

- Matching business_domain
- Matching knowledge_type

## Lower Priority

- Matching artifact_type
- Matching mechanism

## Suppression Rules

transport_behavior and payload chunks should be suppressed unless:
- explicitly requested
- operational evidence is insufficient
- troubleshooting requires them

internal_only chunks must never reach generation.