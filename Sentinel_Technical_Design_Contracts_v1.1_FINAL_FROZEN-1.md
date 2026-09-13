# Sentinel — Technical Design & Contracts v1.1
## FINAL CONTRACT FREEZE

**Status:** FROZEN  
**Supersedes:** Technical Design & Contracts v1  
**Scope:** Contract layer for Sentinel implementation  
**Freeze gate:** Must be accepted before Phase 6 (Policy) implementation

---

# 1. Purpose

This document is the canonical contract between Sentinel services, agents, tools, persistence layers, and the analyst UI.

It converts the frozen system architecture into implementation-level contracts so that individual services can be built independently without changing safety boundaries.

The governing safety principle is:

> **Probabilistic AI investigates and reasons. Deterministic policy controls automated disposition. Humans retain authority over blocking and overrides.**

The most important authority guarantee is:

> **There is no automated BLOCK_HOLD and no AUTO_DECLINE. Only a human analyst may execute BLOCK_HOLD.**

---

# 2. Contract Principles

## 2.1 AI is advisory; Policy is deterministic

Gemini may investigate evidence, identify supporting and counter factors, assess risk categorically, retrieve and compare precedents, and recommend a disposition.

Gemini may not clear a transaction, block or hold a transaction, move money, modify policy rules, or invoke mutating tools.

## 2.2 Policy is the sole automated action authority

The deterministic Policy Decision Service may produce only:

```text
AUTO_RESOLVE
ESCALATE
```

It may never produce `BLOCK_HOLD`.

`BLOCK_HOLD` is exclusively a human analyst action.

## 2.3 Human decisions remain authoritative

An escalated case may be finalized by an analyst as:

```text
CLEAR
BLOCK_HOLD
ESCALATE_SENIOR
```

## 2.4 Evidence completeness is deterministic

The Evidence Agent may choose tools dynamically, but an explicit minimum-evidence floor determines whether the resulting evidence bundle can be marked complete.

## 2.5 All important decisions are traceable

Every detection, evidence bundle, model output, policy decision, human action, and relevant event carries version/provenance information.

---

# 3. Naming and Versioning

## 3.1 IDs

Required identifiers:

```text
transaction_id
case_id
evidence_bundle_id
findings_id
policy_decision_id
event_id
correlation_id
```

## 3.2 Version fields

Model-generated outputs must carry:

```text
model_name
model_version
prompt_version
```

Policy decisions must carry:

```text
rule_id
rule_version
```

Event contracts must carry:

```text
event_type
event_version
```

---

# 4. Transaction Contract

```text
Transaction {
  transaction_id: string
  customer_id: string
  account_id: string
  merchant_id: string
  amount: decimal
  currency: string
  timestamp: timestamp
  device_id: string
  ip_address: string
  geo: {
    lat: decimal
    lon: decimal
    country: string
  }
  channel: string
  merchant_category: string
  transaction_type: string
}
```

### Contract rules

- `transaction_id` is globally unique.
- The transaction is immutable after ingestion.
- A transaction may have at most one active investigation case.
- Duplicate case creation for the same `transaction_id` must be rejected or merged.
- `transaction_id` is an idempotency boundary in addition to `event_id`.

---

# 5. Case Contract

```text
Case {
  case_id: string
  transaction_id: string
  state: CaseState
  created_at: timestamp
  updated_at: timestamp
  detection: DetectionOutput
  evidence_bundle_id?: string
  findings_id?: string
  policy_decision_id?: string
  assigned_analyst_id?: string
  final_disposition?: HumanAction
}
```

## 5.1 Case states

```text
RECEIVED
DETECTED
FLAGGED
INVESTIGATING
EVIDENCE_READY
EVIDENCE_PARTIAL
REASONED
REASONING_FAILED
POLICY_EVALUATED
AUTO_RESOLVED
ESCALATED
HUMAN_REVIEW
FINALIZED
```

## 5.2 State authority

State transitions are controlled by the service responsible for the corresponding stage.

No model output may directly transition a case to `AUTO_RESOLVED`, `ESCALATED`, or `FINALIZED`.

---

# 6. Detection Contract

```text
DetectionOutput {
  case_id: string
  transaction_id: string
  risk_score: decimal
  risk_band: LOW | MEDIUM | HIGH
  anomaly_tags: AnomalyTag[]
  detection_reasons: string[]
  model_name: string
  model_version: string
  detected_at: timestamp
}
```

## 6.1 Risk score

`risk_score` is the measurable detector signal.

It is the numeric signal used for calibrated detector evaluation. Gemini confidence must not be treated as a calibrated probability.

## 6.2 Deterministic anomaly tagging

`anomaly_tags[]` are produced by a deterministic post-processing step from transaction/customer/context features. They are not a hidden second AI model.

Allowed tags:

```text
NEW_DEVICE
UNUSUAL_LOCATION
IMPOSSIBLE_TRAVEL
UNUSUAL_AMOUNT
UNUSUAL_TIME
MERCHANT_RISK
LINKED_ENTITY_ANOMALY
KYC_ANOMALY
```

---

# 7. Evidence Fact Contract

```text
Fact {
  fact_id: string
  type: string
  subject_id: string
  value: object
  source_tool: string
  source_record_id?: string
  observed_at: timestamp
  retrieved_at: timestamp
  quality: VERIFIED | DERIVED | PARTIAL
}
```

Every material evidence claim must be traceable to one or more `fact_id` values.

---

# 8. Evidence Bundle Contract

```text
EvidenceBundle {
  evidence_bundle_id: string
  case_id: string
  facts: Fact[]
  tools_called: string[]
  required_tools: string[]
  completeness: COMPLETE | PARTIAL
  missing_required_evidence: string[]
  conflicts: string[]
  started_at: timestamp
  completed_at: timestamp
}
```

## 8.1 Completeness rule

`COMPLETE` may be emitted only when:

1. the Evidence Agent has satisfied the deterministic minimum-evidence floor for the case's anomaly tags, and
2. no required evidence remains unavailable.

The agent's own judgment may request additional evidence, but it cannot bypass the minimum floor.

---

# 9. Evidence Agent Contract

## 9.1 Input

```text
EvidenceAgentInput {
  case_id: string
  transaction: Transaction
  detection: DetectionOutput
}
```

## 9.2 Output

```text
EvidenceAgentOutput {
  evidence_bundle: EvidenceBundle
  agent_trace: {
    selected_tools: string[]
    selection_reasons: string[]
    stopped_reason: string
  }
  model_name: string
  model_version: string
}
```

## 9.3 Agent constraints

The Evidence Agent:

- is genuinely agentic,
- may dynamically select the next relevant read-only tool,
- may react to facts discovered by previous tools,
- has a maximum of 6 tool calls,
- has a total execution deadline,
- has per-tool timeouts,
- uses an explicit tool allow-list,
- cannot call mutating tools,
- cannot change Policy rules,
- has no hidden cross-case memory.

## 9.4 Minimum evidence floor

The agent's dynamic tool selection sits above a deterministic floor.

Illustrative mapping:

```text
NEW_DEVICE
  -> get_device_history

UNUSUAL_LOCATION
  -> get_ip_geovelocity

IMPOSSIBLE_TRAVEL
  -> get_ip_geovelocity
  -> get_device_history

UNUSUAL_AMOUNT
  -> get_behavioral_baseline

UNUSUAL_TIME
  -> get_behavioral_baseline

MERCHANT_RISK
  -> get_merchant_risk

LINKED_ENTITY_ANOMALY
  -> get_linked_entities

KYC_ANOMALY
  -> get_mock_kyc_status
```

For combinations, the union of required tools is the minimum floor.

---

# 10. Evidence Tool Contracts

All Evidence Agent tools are read-only.

## 10.1 get_device_history

```text
Input:
  customer_id
  device_id

Output:
  known_device: boolean
  first_seen_at: timestamp
  last_seen_at: timestamp
  transaction_count: integer
  device_risk_signals: object[]
  source_record_ids: string[]
```

## 10.2 get_ip_geovelocity

```text
Input:
  customer_id
  current_ip
  current_geo
  transaction_timestamp

Output:
  previous_location: object
  previous_timestamp: timestamp
  distance_km: decimal
  elapsed_hours: decimal
  impossible_travel: boolean
  source_record_ids: string[]
```

## 10.3 get_behavioral_baseline

```text
Input:
  customer_id
  transaction

Output:
  typical_amount: decimal
  amount_deviation: decimal
  typical_hours: object
  time_deviation: decimal
  historical_transaction_count: integer
  source_record_ids: string[]
```

## 10.4 get_linked_entities

```text
Input:
  customer_id
  account_id

Output:
  linked_customers: string[]
  linked_accounts: string[]
  recent_anomalies: object[]
  relationship_signals: object[]
  source_record_ids: string[]
```

## 10.5 get_merchant_risk

```text
Input:
  merchant_id
  merchant_category

Output:
  merchant_risk_band: LOW | MEDIUM | HIGH
  risk_reasons: string[]
  source_record_ids: string[]
```

## 10.6 get_mock_kyc_status

```text
Input:
  customer_id

Output:
  kyc_status: VERIFIED | REVIEW | FAILED
  kyc_flags: string[]
  source_record_ids: string[]
```

---

# 11. Shared Recent-Anomaly Cache

A short-TTL Firestore cache supports order-independent linked-account correlation.

```text
recent_anomalies/{account_id} {
  account_id
  anomalies[]
  observed_at
  expires_at
}
```

## Rules

- TTL is short-lived.
- It is correlation support, not the system of record.
- It does not replace BigQuery history.
- It does not give agents hidden cross-case memory.
- Expired records are ignored.
- The production design may evolve this into richer entity/ring detection.

The hackathon scope is **single-incident correlation, not full fraud-ring detection**.

---

# 12. Tool Failure Semantics

If a tool fails:

1. Retry up to the bounded retry limit.
2. Continue with remaining safe tools where possible.
3. Mark unavailable evidence explicitly.
4. Produce `PARTIAL` evidence if the minimum floor cannot be satisfied.
5. Policy must escalate partial-evidence cases.

A degraded system escalates more cases rather than silently auto-resolving uncertain cases.

---

# 13. Gemini Reasoning Contract

For v1, the Reasoning component is a **Gemini reasoning service**, not a second autonomous tool-selection agent.

It receives a completed/partial EvidenceBundle and produces structured findings.

```text
CaseFindings {
  findings_id: string
  case_id: string
  risk_assessment: LOW | MEDIUM | HIGH
  summary: string
  supporting_factors: FindingFactor[]
  counter_factors: FindingFactor[]
  evidence_gaps: string[]
  evidence_citations: Citation[]
  recommended_disposition: CLEAR | ESCALATE | BLOCK_HOLD
  generated_at: timestamp
  model_name: string
  model_version: string
  prompt_version: string
}
```

## 13.1 Critical safety clarification

`recommended_disposition = BLOCK_HOLD` is **advisory only**.

Gemini may recommend `BLOCK_HOLD` for an analyst to consider, but:

- Gemini cannot execute it.
- Policy cannot execute it.
- No automated service can execute it.
- Only a human analyst may execute `BLOCK_HOLD`.

## 13.2 Gemini uncertainty

Gemini's categorical `risk_assessment` is used as a structured reasoning signal.

Any displayed Gemini confidence/uncertainty is informational only and is not treated as a calibrated probability or sole basis for automated action.

---

# 14. Finding Factor Contract

```text
FindingFactor {
  statement: string
  fact_ids: string[]
  materiality: HIGH | MEDIUM | LOW
}
```

Every material supporting/counter factor should reference the evidence facts used to derive it.

---

# 15. Citation Contract

```text
Citation {
  claim_id: string
  fact_ids: string[]
  precedent_ids?: string[]
}
```

Citation validation in v1 guarantees **structural groundedness**:

- citation exists,
- referenced fact/precedent exists,
- referenced IDs are valid.

It does not claim full semantic verification that the cited evidence necessarily supports every wording nuance of the generated claim.

A stronger second-pass semantic verifier is a production improvement.

---

# 16. RAG Precedent Contract

```text
Precedent {
  precedent_id: string
  case_summary: string
  anomaly_tags: string[]
  outcome: string
  evidence_summary: string
  source_type: string
  created_at: timestamp
}
```

Reasoning retrieves relevant precedents from Vertex AI Vector Search.

The demo must visibly show:

1. retrieved precedent,
2. similarity/relevance,
3. important similarity or difference,
4. how that comparison influenced the reasoning.

The precedent corpus is curated/synthetic for the hackathon and must not be presented as independent real-world ground truth.

---

# 17. Policy Rule Contract

Policy rules are versioned data.

```text
PolicyRule {
  rule_id: string
  version: string
  priority: integer
  condition: string
  outcome: AUTO_RESOLVE | ESCALATE
  effective_from: timestamp
  enabled: boolean
}
```

## 17.1 Non-negotiable authority boundary

The PolicyRule outcome enum is intentionally limited to:

```text
AUTO_RESOLVE
ESCALATE
```

It does **not** contain `BLOCK_HOLD`.

Therefore a policy rule cannot be authored to automatically block/hold a transaction.

---

# 18. Mandatory Policy Rules

These rules are part of the frozen contract, not optional illustrations.

## Rule P-001 — Incomplete evidence

```text
IF evidence.completeness = PARTIAL
    -> ESCALATE
```

## Rule P-002 — Risk-assessment tightening

```text
IF risk_score >= MEDIUM
AND findings.risk_assessment = HIGH
AND evidence.completeness = COMPLETE
    -> ESCALATE
```

This rule is deliberately included because Gemini's structured risk assessment must measurably affect deterministic system behavior without giving Gemini action authority.

## Rule P-003 — High-value transactions

The high-value threshold remains an evaluation-tuned parameter.

The final threshold must be selected from the held-out evaluation set using an explicit precision/recall or cost-of-error tradeoff and recorded with the rule version.

## Rule P-004 — Low-risk eligible cases

Auto-resolution may occur only when all configured deterministic eligibility conditions are satisfied, including complete evidence and applicable risk thresholds.

No rule may produce `BLOCK_HOLD`.

---

# 19. Policy Decision Contract

```text
PolicyDecision {
  decision_id: string
  case_id: string
  outcome: AUTO_RESOLVE | ESCALATE
  rule_id: string
  rule_version: string
  reasons: string[]
  inputs_snapshot: object
  evaluated_at: timestamp
}
```

## 19.1 Policy authority

Policy is the sole automated disposition authority.

It may:

```text
AUTO_RESOLVE
ESCALATE
```

It may never:

```text
BLOCK_HOLD
AUTO_DECLINE
```

A policy decision cannot directly create a human `BLOCK_HOLD`.

---

# 20. Human Decision Contract

```text
HumanDecisionRequest {
  case_id: string
  analyst_id: string
  action: CLEAR | BLOCK_HOLD | ESCALATE_SENIOR
  reason?: string
  evidence_acknowledged: boolean
  client_timestamp: timestamp
}
```

## 20.1 Human authority

Only a human analyst may execute:

```text
BLOCK_HOLD
```

`ESCALATE_SENIOR` is explicitly an analyst action and is distinct from the system-level case state `ESCALATED`.

## 20.2 Analyst acknowledgement

The analyst must acknowledge at least one evidence factor before a final action/override is enabled in the UI.

This reduces automation bias and ensures the human-in-the-loop is substantive rather than ceremonial.

---

# 21. Event Envelope

All Pub/Sub messages use:

```text
EventEnvelope<T> {
  event_id: string
  event_type: string
  event_version: string
  case_id?: string
  transaction_id?: string
  correlation_id: string
  occurred_at: timestamp
  producer: string
  payload: T
}
```

## 21.1 Initial event types

```text
TransactionReceived
CaseFlagged
EvidenceReady
CaseReasoned
PolicyEvaluated
HumanDecisionSubmitted
```

## 21.2 Topics

```text
transactions.raw
cases.flagged
cases.evidence_ready
cases.reasoned
feedback.human_decisions
```

---

# 22. Idempotency Contract

## Event-level idempotency

`event_id` must be unique.

Repeated delivery of the same event must not create duplicate side effects.

## Transaction-level idempotency

`transaction_id` must be unique at case creation.

If an already-open case exists for a transaction:

```text
do not create a second independent investigation
```

The implementation must reject, merge, or return the existing case.

## Decision-level idempotency

A policy decision is uniquely associated with a case evaluation/version.

Human decisions must not be applied twice for the same human action request.

---

# 23. Audit Contract

```text
AuditEvent {
  audit_event_id: string
  case_id: string
  transaction_id: string
  event_type: string
  actor_type: SYSTEM | AGENT | HUMAN
  actor_id?: string
  model_name?: string
  model_version?: string
  rule_id?: string
  rule_version?: string
  input_snapshot?: object
  output_snapshot?: object
  occurred_at: timestamp
  correlation_id: string
}
```

The hackathon implementation uses a restricted append-oriented BigQuery audit table.

Do not describe it as WORM/cryptographically immutable unless those controls are actually implemented.

---

# 24. Error Contract

```text
ErrorEnvelope {
  error_code: string
  message: string
  retryable: boolean
  case_id?: string
  transaction_id?: string
  correlation_id: string
  occurred_at: timestamp
}
```

## Required fail-safe behavior

```text
Gemini unavailable
    -> retry boundedly
    -> escalation if still unavailable

Tool unavailable
    -> bounded retry
    -> partial evidence / escalation

Malformed Gemini output
    -> one schema-only reprompt
    -> escalation if second failure

Pub/Sub delivery failure
    -> native retry
    -> DLQ
    -> scheduled sweep
    -> escalation queue

Database failure
    -> bounded client retry
    -> pause rather than proceed with unsaved state
```

The invariant is:

> **When in doubt, Sentinel does less, not more.**

---

# 25. DLQ Fail-Safe Sweep

The scheduled fail-safe sweep is part of the implementation contract.

Hackathon target:

```text
every 60 seconds
```

The sweep identifies cases that have remained stuck in retry/DLQ conditions beyond the configured safety window and places them into the escalation queue.

---

# 26. Service API Boundaries

## 26.1 Detection Service

```text
POST /v1/detection/evaluate
```

Input: `Transaction`  
Output: `DetectionOutput`

Responsibilities:
- model inference,
- deterministic anomaly tagging,
- case creation/idempotency boundary.

## 26.2 Evidence Agent

```text
POST /v1/cases/{case_id}/investigate
```

Input: `Transaction + DetectionOutput`  
Output: `EvidenceAgentOutput`

Responsibilities:
- dynamic read-only tool selection,
- minimum-evidence floor,
- bounded execution,
- evidence provenance.

## 26.3 Reasoning Service

```text
POST /v1/cases/{case_id}/reason
```

Input: `EvidenceBundle`  
Output: `CaseFindings`

Responsibilities:
- Gemini structured reasoning,
- precedent retrieval,
- citation generation,
- schema validation.

## 26.4 Policy Service

```text
POST /v1/cases/{case_id}/policy/evaluate
```

Input: `DetectionOutput + EvidenceBundle + CaseFindings`  
Output: `PolicyDecision`

Responsibilities:
- deterministic rule evaluation,
- exact rule-version recording,
- automated disposition only.

## 26.5 Human Decision API

```text
POST /v1/cases/{case_id}/human-decision
```

Input: `HumanDecisionRequest`  
Output: `FinalizedCase`

Only this path may execute `BLOCK_HOLD`.

---

# 27. Service Account Boundaries

## Generator

`generator-sa`

May publish synthetic transactions. It may not access Policy, modify cases, or call mutating tools.

## Detection

`detection-sa`

May read model artifacts, publish case events, and write detection results. It may not execute human actions.

## Evidence Agent

`evidence-agent-sa`

May read approved evidence tools and write investigation state required for its stage. It may not mutate transactional state, execute Policy actions, or execute `BLOCK_HOLD`.

## Reasoning

`reasoning-agent-sa`

May read Vector Search and evidence bundles. It may not call transactional mutation tools, execute Policy actions, or execute `BLOCK_HOLD`.

## Policy

`policy-sa`

May read required case inputs, evaluate versioned rules, and write PolicyDecision. It may not produce `BLOCK_HOLD`.

## Human/UI

The analyst identity is authenticated and authorized separately. Only the human decision path can finalize `BLOCK_HOLD`.

---

# 28. Data Responsibilities

## Firestore

Use for:
- live case state,
- open investigation queue,
- analyst workflow state,
- short-TTL recent-anomaly cache.

## BigQuery

Use for:
- historical transaction data,
- append-oriented audit events,
- evaluation datasets/results,
- policy rule versions where appropriate.

## Vertex AI Vector Search

Use for curated precedent retrieval.

## Cloud Storage

Use for model/evaluation artifacts where required.

---

# 29. Query and Index Requirements

## Firestore

Primary access patterns:

```text
case_id lookup
open cases by state
cases assigned to analyst
recent anomaly lookup by account_id
```

Required indexes should be created only for actual query patterns.

The recent-anomaly cache must use TTL expiration.

## BigQuery

Historical/evaluation tables should be partitioned by event/transaction date.

Audit and transaction access should be clustered around common investigation dimensions such as:

```text
case_id
transaction_id
customer_id
```

Exact clustering should be validated against the implemented query workload rather than added indiscriminately.

---

# 30. Local Development Contract

Local development must preserve the same logical contracts.

Recommended topology:

```text
Generator
   |
   v
Pub/Sub emulator / local event bus
   |
Detection
   |
Evidence Agent
   |
Mock Tools
   |
Reasoning / Gemini
   |
Policy
   |
Firestore emulator / local store
   |
Analyst UI
```

Production topology maps the same contracts to:

```text
Cloud Run
Pub/Sub
Firestore
BigQuery
Vertex AI / Gemini
Vertex AI Vector Search
Cloud Logging / Trace / Monitoring
```

---

# 31. Observability Contract

Every stage must propagate:

```text
case_id
transaction_id
correlation_id
```

Track at minimum:

- end-to-end latency,
- per-stage latency,
- detector flag rate,
- Evidence Agent tool calls,
- evidence completeness,
- Gemini failures,
- schema-validation failures,
- policy outcomes,
- escalation rate,
- human decision latency,
- DLQ count,
- stuck-case count.

---

# 32. Evaluation Contract

The evaluation harness must measure separately.

## Detection

```text
precision
recall
ROC-AUC / PR-AUC
false-negative rate
```

## Evidence Agent

```text
required-evidence completion
tool-selection quality
tool-call count
latency
```

## Reasoning

```text
structured-output validity
citation validity
structural groundedness
risk-assessment agreement
```

## End-to-end

```text
decision accuracy
safe escalation rate
automation rate
analyst time saved
latency
cost per flagged case
```

Thresholds must be selected using held-out evaluation data, not arbitrary demo intuition.

---

# 33. Safety Invariants — FINAL

These are non-negotiable implementation tests.

### Invariant 1

```text
Gemini cannot directly execute an action.
```

### Invariant 2

```text
Policy cannot produce BLOCK_HOLD.
```

### Invariant 3

```text
Policy cannot produce AUTO_DECLINE.
```

### Invariant 4

```text
Only a human analyst can execute BLOCK_HOLD.
```

### Invariant 5

```text
Partial required evidence cannot auto-resolve.
```

### Invariant 6

```text
Every automated Policy decision records rule_id + rule_version.
```

### Invariant 7

```text
Every material reasoning factor is traceable to evidence.
```

### Invariant 8

```text
Duplicate delivery cannot create duplicate side effects.
```

### Invariant 9

```text
Duplicate case creation for the same transaction is prevented.
```

### Invariant 10

```text
A stuck/failing case eventually reaches the fail-safe escalation path.
```

---

# 34. Implementation Order

The frozen implementation sequence is:

```text
1. Synthetic transaction generator
2. Transaction + Case contracts
3. Detection model
4. Deterministic anomaly tagging
5. Evidence tools
6. Evidence Agent
7. Recent-anomaly cache
8. Gemini reasoning + RAG
9. Structural citation/schema validation
10. Policy rules + versioning
11. Human decision path
12. Firestore analyst queue
13. BigQuery audit/evaluation
14. Pub/Sub retries + DLQs
15. 60-second fail-safe sweep
16. Observability
17. Offline evaluation
18. Signal-removal demo + rehearsed fallback
```

Phase 6 Policy must not begin until Sections 17–20 are implemented exactly as frozen.

---

# 35. Explicit Build / Don't-Build Boundary

## Build

- synthetic transaction generator,
- real detector model on public labeled data,
- deterministic anomaly tagging,
- genuine bounded Evidence Agent,
- six read-only evidence tools,
- recent-anomaly cache,
- Gemini structured reasoning,
- RAG precedent retrieval,
- structural citation validation,
- deterministic versioned Policy,
- Firestore live case queue,
- analyst UI,
- human `CLEAR / BLOCK_HOLD / ESCALATE_SENIOR`,
- BigQuery audit/evaluation,
- Pub/Sub event backbone,
- DLQs,
- 60-second fail-safe sweep,
- observability,
- offline evaluation,
- signal-removal demonstration with rehearsed fallback.

## Do not build

- graph database,
- real KYC/merchant API integrations,
- custom fine-tuned Gemini,
- custom GNN,
- autonomous policy learning,
- multi-tenant SaaS,
- half-built fairness pipeline,
- chat interface as primary analyst surface.

---

# 36. Final Authority Model

```text
Detection
  |
  | risk_score + anomaly_tags
  v
Evidence Agent
  |
  | read-only investigation
  v
Gemini Reasoning
  |
  | CaseFindings
  | BLOCK_HOLD may be recommended
  | but is advisory only
  v
Deterministic Policy
  |
  +--> AUTO_RESOLVE
  |
  +--> ESCALATE
          |
          v
     Human Analyst
          |
          +--> CLEAR
          +--> BLOCK_HOLD
          +--> ESCALATE_SENIOR
```

The critical distinction is:

```text
SYSTEM ESCALATION       = ESCALATE
HUMAN ESCALATION         = ESCALATE_SENIOR
HUMAN BLOCK              = BLOCK_HOLD
AUTOMATED BLOCK          = NOT ALLOWED
```

---

# 37. Freeze Statement

**Sentinel Technical Design & Contracts v1.1 is frozen for implementation.**

No implementation may introduce an automated `BLOCK_HOLD` path, `AUTO_DECLINE`, or any equivalent automated blocking behavior.

Any future change to these safety boundaries requires an explicit architecture review and contract-version change.

**Next implementation phase: Concrete Data & API Design / Phase 2, with Phase 6 Policy implementation gated on these frozen authority contracts.**
