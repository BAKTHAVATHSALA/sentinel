# Sentinel — Technical Design & Contracts v1.2
## V1 SCOPE-ALIGNED CONTRACT FREEZE

**Status:** FROZEN
**Supersedes:** Technical Design & Contracts v1.1 (FINAL FROZEN)
**Scope:** Contract layer for the Sentinel **V1 hackathon build only** — synced against
V1 Build Architecture v1.1 (domain-scoped) and the V1 Build Checklist.
**Freeze gate:** Must be accepted before Phase 4 (Policy) implementation.

---

# 0. Change Log — why v1.1 → v1.2

v1.1 was frozen ahead of the domain-scope resolution and described a larger,
production-shaped system (multi-service topology, Pub/Sub, BigQuery, Vector
Search/RAG) than what the Build Architecture v1.1 and the Build Checklist
actually call for in V1. This version brings the contract layer back in sync
with those two documents. Nothing in the *authority model* changed — Gemini is
still advisory-only, Policy still only ever produces `AUTO_RESOLVE`/`ESCALATE`,
and only a human can execute `BLOCK_HOLD`.

| Change | Reason |
|---|---|
| `Transaction` contract updated: added `payment_rail`, `direction`, `authorization_stage`, `card_id`, `card_present`; narrowed `channel` to `WEB \| MOBILE`; removed `transaction_type` | Bring in sync with Build Architecture v1.1 §3, which resolved the domain/business ambiguity |
| Added a **Domain Entities** contract (Customer, Account, Card, Merchant, Device, IP/Location) | These were referenced by the architecture and checklist but never contract-defined |
| `get_merchant_risk()` output replaced with the v1.1 investigable shape | Old shape was a static label (`merchant_risk_band`, `risk_reasons[]`); new shape adds `recent_fraud_report_count`, `fraud_report_trend`, `customer_prior_transactions_with_merchant` |
| Anomaly tag list trimmed to the 5 V1 tags, `KYC_ANOMALY` marked optional, `IMPOSSIBLE_TRAVEL`/`UNUSUAL_TIME` moved to out-of-scope | These two tags don't apply to the locked CNP scenario and the checklist explicitly drops them for V1 |
| Added a **Decision Robustness Scorer** contract, and a `robustness` field on `Case` | Core V1 component (fast-path + live counterfactual, ROBUST/FRAGILE) had no formal contract before |
| Added missing Policy rules P-002 (`reasoning.status = FAILED → ESCALATE`) and P-006 (default `OTHERWISE → ESCALATE`) | Both are required by the architecture's rule set and the checklist but were absent from the v1.1 rule list |
| Removed Pub/Sub Event Envelope, topics, BigQuery sections, Vertex AI Vector Search/RAG contract, DLQ scheduled sweep, and per-service service accounts | V1 is one Cloud Run service, in-process modules, a synchronous pipeline, and Firestore-only storage — none of the removed items exist in V1 |
| Rewrote Service API Boundaries as one ingestion endpoint + analyst endpoints, all backed by in-process module calls | Matches the checklist's single entry point: `POST /transactions → Detection → Evidence Agent → Reasoning → Robustness Scorer → Policy → Firestore write` |
| Rewrote Implementation Order and Build/Don't-Build Boundary | Old lists still referenced the removed infrastructure and a standalone generator service |

Everything not listed above — the core authority principles, the Evidence Agent's
constraints, citation validation, the tool contracts other than `get_merchant_risk`,
the human decision contract — is unchanged and still correct.

---

# 1. Purpose

This document is the canonical contract between Sentinel's modules, tools,
persistence layer, and the analyst UI for **V1**.

It converts the frozen system architecture into implementation-level contracts
so that individual modules can be built independently without changing safety
boundaries.

The governing safety principle is:

> **Probabilistic AI investigates and reasons. Deterministic policy controls automated disposition. Humans retain authority over blocking and overrides.**

The most important authority guarantee is:

> **There is no automated `BLOCK_HOLD` and no `AUTO_DECLINE`. Only a human analyst may execute `BLOCK_HOLD`.**

---

# 2. Contract Principles

## 2.1 AI is advisory; Policy is deterministic

Gemini may investigate evidence, identify supporting and counter factors,
assess risk categorically, and recommend a disposition.

Gemini may not clear a transaction, block or hold a transaction, move money,
modify policy rules, or invoke mutating tools.

## 2.2 Policy is the sole automated action authority

The deterministic Policy module may produce only:

```text
AUTO_RESOLVE
ESCALATE
```

It may never produce `BLOCK_HOLD`.

## 2.3 Human decisions remain authoritative

An escalated case may be finalized by an analyst as:

```text
CLEAR
BLOCK_HOLD
ESCALATE_SENIOR
```

## 2.4 Evidence completeness is deterministic

The Evidence Agent may choose tools dynamically, but an explicit
minimum-evidence floor determines whether the resulting evidence bundle can be
marked complete.

## 2.5 All important decisions are traceable

Every detection, evidence bundle, model output, robustness result, policy
decision, and human action carries version/provenance information.

---

# 3. Naming and Versioning

## 3.1 IDs

```text
transaction_id
case_id
evidence_bundle_id
findings_id
robustness_id
policy_decision_id
audit_event_id
correlation_id
```

`correlation_id` is a per-request trace ID (there is no message bus in V1 to
correlate across — it exists purely for log tracing across modules within one
request).

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

---

# 4. Domain Scope (V1)

**Scenario: card-not-present (CNP) e-commerce purchase, outgoing, pre-authorization.**

Explicitly out of scope for V1 (name if asked, don't build): UPI/real-time peer
transfers, IMPS/NEFT/RTGS bank transfers, ATM withdrawals, incoming/receiving-side
fraud (mule-account detection). Adding a rail later means extending
`payment_rail` as an enum and adding rail-specific evidence tools — not
rebuilding the pipeline. See Build Architecture v1.1 §1 and §9 for the full
rationale and extension path.

---

# 5. Domain Entities

These are the concrete entities the fixture data and evidence tools operate
over. They extend, not replace, the contracts in this document.

```text
Customer {
  customer_id: string
  tenure_months: integer
  kyc_status: string
}

Account {
  account_id: string
  customer_id: string
  status: string
  linked_account_ids: string[]
}

Card {
  card_id: string
  account_id: string
  issued_at: timestamp
  card_present: boolean
}

Merchant {
  merchant_id: string
  category: string
  onboarding_date: date
  chargeback_rate: decimal
  recent_fraud_reports: object[]
  risk_band: LOW | MEDIUM | HIGH
}

Device {
  device_id: string
  first_seen: timestamp
  linked_customer_ids: string[]
}

IPLocation {
  ip_address: string
  geo: { lat: decimal, lon: decimal, country: string }
  asn: string
  first_seen: timestamp
}
```

For the V1 fixture: the customer is existing with an 18-month tenure
(established behavioral baseline exists); the merchant is new-to-this-customer;
the device is new (first seen ~40 minutes before the transaction); the
IP/location is unusual versus the customer's established pattern (not
impossible-travel).

---

# 6. Transaction Contract

```text
Transaction {
  transaction_id: string
  customer_id: string
  account_id: string
  card_id: string
  merchant_id: string

  amount: decimal
  currency: string
  timestamp: timestamp

  payment_rail: CARD_CNP                          # enum, one value populated in V1
  direction: OUTGOING
  authorization_stage: PRE_AUTH | AUTH | SETTLED  # V1 operates at PRE_AUTH

  device_id: string
  ip_address: string
  geo: { lat: decimal, lon: decimal, country: string }

  channel: WEB | MOBILE                            # narrowed — POS/ATM not relevant to CNP
  merchant_category: string
  card_present: boolean                            # false for the V1 scenario
}
```

### Contract rules

- `transaction_id` is globally unique.
- The transaction is immutable after ingestion.
- A transaction may have at most one active investigation case.
- Duplicate case creation for the same `transaction_id` must be rejected or merged.
- `payment_rail` being an enum (not free text) is what makes adding a rail later
  a low-friction extension instead of a rewrite.

---

# 7. Case Contract

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
  robustness?: RobustnessResult
  policy_decision_id?: string
  assigned_analyst_id?: string
  final_disposition?: HumanAction
}
```

## 7.1 Case states

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

## 7.2 State authority

State transitions are controlled server-side, by the module responsible for
the corresponding pipeline stage. No client/UI code and no model output may
directly set case state.

No model output may directly transition a case to `AUTO_RESOLVED`,
`ESCALATED`, or `FINALIZED`.

---

# 8. Detection Contract

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

## 8.1 Risk score

`risk_score` is the measurable detector signal, evaluated against a real
public labeled dataset (held-out precision/recall/ROC-AUC/PR-AUC). Gemini
confidence is never treated as a calibrated probability.

## 8.2 Deterministic anomaly tagging

`anomaly_tags[]` are produced by a deterministic post-processing step from
transaction/customer/context features — not a hidden second AI model.

**V1 tags (in scope):**

```text
NEW_DEVICE
UNUSUAL_LOCATION
UNUSUAL_AMOUNT
MERCHANT_RISK
LINKED_ENTITY_ANOMALY
```

**Optional for V1** (keep only if cheap to add):

```text
KYC_ANOMALY   -> get_mock_kyc_status
```

**Out of scope for V1** (do not implement — not meaningful for the locked CNP
scenario; revisit only if a rail requiring them is added):

```text
IMPOSSIBLE_TRAVEL
UNUSUAL_TIME
```

---

# 9. Evidence Fact Contract

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

# 10. Evidence Bundle Contract

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

## 10.1 Completeness rule

`COMPLETE` may be emitted only when:

1. the Evidence Agent has satisfied the deterministic minimum-evidence floor
   for the case's anomaly tags, and
2. no required evidence remains unavailable.

The agent's own judgment may request additional evidence, but it cannot
bypass the minimum floor.

---

# 11. Evidence Agent Contract

## 11.1 Input

```text
EvidenceAgentInput {
  case_id: string
  transaction: Transaction
  detection: DetectionOutput
}
```

## 11.2 Output

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

## 11.3 Agent constraints

The Evidence Agent:

- is genuinely agentic — it may dynamically select the next relevant
  read-only tool and react to facts discovered by previous tools,
- has a maximum of 6 tool calls,
- has a total execution deadline and per-tool timeouts,
- uses an explicit tool allow-list (Gemini Flash),
- cannot call mutating tools, change Policy rules, or execute `BLOCK_HOLD`,
- has no hidden cross-case memory.

`stopped_reason` is one of: `SUFFICIENT_EVIDENCE`, `MAX_CALLS`, `TIMEOUT`,
`TOOL_FAILURE`, `FLOOR_SATISFIED`.

## 11.4 Minimum evidence floor

```text
NEW_DEVICE            -> get_device_history
UNUSUAL_LOCATION      -> get_ip_geovelocity
MERCHANT_RISK         -> get_merchant_risk
UNUSUAL_AMOUNT        -> get_behavioral_baseline
LINKED_ENTITY_ANOMALY -> get_linked_entities
KYC_ANOMALY (optional) -> get_mock_kyc_status
```

For combinations, the union of required tools is the minimum floor. The agent
cannot mark completeness `COMPLETE` until the floor is satisfied, even if
Gemini "thinks" it's done earlier.

---

# 12. Evidence Tool Contracts

All Evidence Agent tools are read-only and run against fixture data in V1
(never a real KYC/merchant API).

## 12.1 get_device_history

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

## 12.2 get_ip_geovelocity

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

## 12.3 get_behavioral_baseline

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

## 12.4 get_linked_entities

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

## 12.5 get_merchant_risk — v1.1 investigable shape

```text
Input:
  merchant_id: string
  customer_id: string

Output:
  category: string
  onboarding_date: date
  chargeback_rate: decimal

  recent_fraud_report_count: number
  fraud_report_trend: RISING | STABLE | FALLING

  customer_prior_transactions_with_merchant: number   # 0 = never transacted before

  risk_band: LOW | MEDIUM | HIGH
```

This is what makes merchant risk genuinely investigable evidence rather than
a static label — `fraud_report_trend` in particular gives the Evidence Agent
and Reasoning something ambiguous to weigh (a few reports could be noise or
signal).

## 12.6 get_mock_kyc_status (optional for V1)

```text
Input:
  customer_id

Output:
  kyc_status: VERIFIED | REVIEW | FAILED
  kyc_flags: string[]
  source_record_ids: string[]
```

---

# 13. Shared Recent-Anomaly Cache

A short-TTL Firestore cache supports order-independent linked-account
correlation.

```text
recent_anomalies/{account_id} {
  account_id
  anomalies[]
  observed_at
  expires_at
}
```

- TTL is short-lived; it is correlation support, not the system of record.
- It does not give agents hidden cross-case memory.
- Expired records are ignored.

The V1 scope is **single-incident correlation, not full fraud-ring detection**.

---

# 14. Tool Failure Semantics

If a tool fails:

1. Retry up to the bounded retry limit.
2. Continue with remaining safe tools where possible.
3. Mark unavailable evidence explicitly.
4. Produce `PARTIAL` evidence if the minimum floor cannot be satisfied.
5. Policy must escalate partial-evidence cases.

A degraded system escalates more cases rather than silently auto-resolving
uncertain ones.

---

# 15. Gemini Reasoning Contract

The Reasoning component is a **Gemini Pro reasoning call**, not a second
autonomous tool-selection agent. It receives a completed/partial
`EvidenceBundle` and produces structured findings.

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

## 15.1 Critical safety clarification

`recommended_disposition = BLOCK_HOLD` is **advisory only**. Gemini may
recommend it for an analyst to consider, but Gemini cannot execute it, Policy
cannot execute it, and no automated path can execute it — only a human
analyst may.

## 15.2 Gemini uncertainty

Gemini's categorical `risk_assessment` is a structured reasoning signal. Any
displayed confidence/uncertainty is informational only, never a calibrated
probability or sole basis for automated action.

---

# 16. Finding Factor Contract

```text
FindingFactor {
  statement: string
  fact_ids: string[]
  materiality: HIGH | MEDIUM | LOW
}
```

---

# 17. Citation Contract

```text
Citation {
  claim_id: string
  fact_ids: string[]
}
```

Citation validation in V1 guarantees **structural groundedness**: the
citation exists, and every referenced `fact_id` exists in the evidence bundle
passed in. It does not claim full semantic verification that the cited
evidence supports every wording nuance of the claim. Precedent retrieval
(RAG) is out of scope for V1 — see §34.

On an invalid or missing citation: reject and reprompt (schema-only, stricter
instruction). On a second failure, mark `reasoning.status = FAILED`, which
flows into Policy as a forced escalation (Rule P-002, §20).

---

# 18. Decision Robustness Scorer Contract

```text
RobustnessResult {
  robustness_id: string
  case_id: string
  classification: ROBUST | FRAGILE
  fragile_factor_id?: string        # fact_id of the factor whose removal flips the outcome, if FRAGILE
  method: FAST_PATH | LIVE_COUNTERFACTUAL
  evaluated_at: timestamp
}
```

## 18.1 Fast-path (default, every case)

For each HIGH-materiality supporting factor in `CaseFindings`, estimate
whether removing it would flip `risk_assessment` below the Policy escalation
threshold. `ROBUST` if no single factor's removal flips the outcome;
`FRAGILE` otherwise.

## 18.2 Live counterfactual (demo path)

Given a specific `fact_id` to remove, rebuild the `EvidenceBundle` without it
and **re-invoke Reasoning for real**. This is the path used in the live demo
moment — not the fast-path estimate.

## 18.3 Authority boundary

`RobustnessResult.classification` is investigative and UI signal only. It is
**not** an input to any Policy rule (§20) — Policy only ever evaluates
`risk_score`, `evidence.completeness`, and `findings.risk_assessment`. Wiring
robustness into automated disposition would be scope creep beyond what V1
(or the frozen architecture) defines.

---

# 19. Policy Rule Contract

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

The outcome enum is intentionally limited to `AUTO_RESOLVE | ESCALATE`. It
does **not** contain `BLOCK_HOLD` — a policy rule cannot be authored to
automatically block/hold a transaction.

---

# 20. Mandatory Policy Rules

These six rules are the complete, frozen V1 rule set — not illustrative.

```text
P-001  IF evidence.completeness = PARTIAL
           -> ESCALATE

P-002  IF reasoning.status = FAILED
           -> ESCALATE

P-003  IF risk_score >= HIGH
       AND value >= HIGH_VALUE
       AND evidence.completeness = COMPLETE
           -> ESCALATE

P-004  IF risk_score >= MEDIUM
       AND findings.risk_assessment = HIGH
       AND evidence.completeness = COMPLETE
           -> ESCALATE

P-005  IF risk_score <= LOW
       AND evidence.completeness = COMPLETE
       AND no hard-risk-tag
       AND findings.risk_assessment != HIGH
           -> AUTO_RESOLVE

P-006  OTHERWISE
           -> ESCALATE
```

`HIGH_VALUE` and the risk-score thresholds are evaluation-tuned parameters —
select them from the held-out evaluation set, not guessed numbers, and record
the chosen values with the rule version.

No rule may produce `BLOCK_HOLD`.

---

# 21. Policy Decision Contract

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

It may never produce `BLOCK_HOLD` or `AUTO_DECLINE`.

---

# 22. Human Decision Contract

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

Only a human analyst may execute `BLOCK_HOLD`. `ESCALATE_SENIOR` is
explicitly an analyst action, distinct from the system-level case state
`ESCALATED`. Reason is required for `BLOCK_HOLD` and `ESCALATE_SENIOR`. The
analyst must acknowledge at least one evidence factor before any final
action is enabled in the UI — this keeps the human-in-the-loop substantive
rather than ceremonial.

---

# 23. Idempotency Contract

## Request-level idempotency

`POST /transactions` for an already-open `transaction_id` must not create a
second independent investigation — reject, merge, or return the existing
case.

## Decision-level idempotency

A `PolicyDecision` is uniquely associated with one case evaluation. A given
`HumanDecisionRequest` action is not applied twice.

---

# 24. Audit Contract

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

Stored as an `audit_events` subcollection under each `cases/{case_id}`
document. Write one entry on every state transition. Do not describe this as
WORM/cryptographically immutable — it isn't, in V1.

---

# 25. Error & Fail-Safe Contract

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

Required fail-safe behavior, all enforced synchronously within the request:

```text
Gemini unavailable
    -> retry boundedly
    -> escalate if still unavailable

Tool unavailable
    -> bounded retry
    -> partial evidence / escalate

Malformed Gemini output
    -> one schema-only reprompt
    -> escalate on second failure

Firestore write failure
    -> bounded client retry
    -> pause rather than proceed with unsaved state
```

The invariant is:

> **When in doubt, Sentinel does less, not more.**

---

# 26. Service & Module API Boundaries

V1 is **one Cloud Run service**. There is a single external API surface;
everything else below it is an in-process module call, not a network call.

## 26.1 External API

```text
POST /transactions
```
Runs the full synchronous pipeline in-process:
`Detection → (if flagged) Evidence Agent → Reasoning → Robustness Scorer → Policy → Firestore write`.
Clean/normal transactions with no anomaly tags skip investigation and resolve
immediately.

```text
GET  /cases                       # queue view — escalated cases, risk band, robustness flag
GET  /cases/{case_id}              # full case detail
POST /cases/{case_id}/decision     # analyst_id, action, reason, evidence_acknowledged
```
`POST /cases/{case_id}/decision` requires the case to be in `HUMAN_REVIEW`
state; the action is idempotent and writes an audit event.

## 26.2 Internal module contracts (function calls, not services)

```text
Detection.predict(transaction) -> risk_score, risk_band
Detection.tag_anomalies(transaction, context) -> anomaly_tags[]
EvidenceAgent.investigate(transaction, detection) -> EvidenceAgentOutput
Reasoning.reason(evidence_bundle) -> CaseFindings
RobustnessScorer.score(findings, evidence_bundle) -> RobustnessResult
Policy.evaluate(detection, evidence_bundle, findings) -> PolicyDecision
```

Each module still respects its own authority boundary (§2) even though it
runs in-process — enforced by code structure and code review, not by network
isolation.

---

# 27. Service Account & Module Authority Boundaries

V1 has **one** Cloud Run service account (least-privilege: Vertex AI User,
Firestore User — never Owner/Editor). Since there is only one deployed
identity, module-level boundaries are enforced in code, not IAM:

- Evidence Agent may call the six approved read-only tools; it may not mutate
  transactional state, execute Policy actions, or execute `BLOCK_HOLD`.
- Reasoning may not call mutation tools, execute Policy actions, or execute
  `BLOCK_HOLD`.
- Policy may read required case inputs and write `PolicyDecision`; it may
  never produce `BLOCK_HOLD`.
- Only the human decision path (§22) can finalize `BLOCK_HOLD`.

Splitting into separate services/service accounts is a valid production
hardening step later, following the same extension pattern as adding a
payment rail (architecture v1.1 §9) — not something V1 needs.

---

# 28. Data Responsibilities

## Firestore (the only datastore in V1)

- live case state (`cases/{case_id}`)
- `audit_events` subcollection per case
- open investigation queue / analyst workflow state
- short-TTL recent-anomaly cache

## Local files

- trained model artifact + `model_name`/`model_version`
- `eval/detection_baseline.json` and `eval/results_summary.md`
- versioned seed fixtures (`data/seed/`)

**Not used in V1:** BigQuery, Vertex AI Vector Search, Pub/Sub, Cloud Storage
(unless a model binary genuinely needs external storage — optional, not
required).

---

# 29. Local Development & Production Topology

Local:

```text
Fixture Loader
   |
   v
Detection
   |
   v
Evidence Agent -> Mock Tools
   |
   v
Reasoning / Gemini
   |
   v
Robustness Scorer
   |
   v
Policy
   |
   v
Firestore emulator / local store
   |
   v
Analyst UI
```

All arrows above are in-process function calls, not a message bus.

Production:

```text
Cloud Run (single service)
Firestore
Vertex AI / Gemini
Cloud Logging / Trace / Monitoring
```

No Pub/Sub, BigQuery, or Vertex AI Vector Search in V1.

---

# 30. Observability Contract

Every stage propagates `case_id`, `transaction_id`, `correlation_id`. Track
at minimum:

```text
end-to-end latency
per-stage latency
detector flag rate
Evidence Agent tool calls
evidence completeness
Gemini failures
schema-validation failures
policy outcomes
escalation rate
human decision latency
stuck-case count (bounded-retry exhaustion)
```

---

# 31. Evaluation Contract

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
latency
```

Thresholds must be selected using held-out evaluation data, not demo intuition.

---

# 32. Safety Invariants — FINAL

```text
1.  Gemini cannot directly execute an action.
2.  Policy cannot produce BLOCK_HOLD.
3.  Policy cannot produce AUTO_DECLINE.
4.  Only a human analyst can execute BLOCK_HOLD.
5.  Partial required evidence cannot auto-resolve.
6.  Every automated Policy decision records rule_id + rule_version.
7.  Every material reasoning factor is traceable to evidence.
8.  Duplicate request delivery cannot create duplicate side effects or cases.
9.  Duplicate case creation for the same transaction is prevented.
10. A request that exhausts its bounded retries (tool failure, Gemini
    failure, malformed output) fails safe to ESCALATE within that same
    request — it never silently drops or auto-resolves.
```

---

# 33. Implementation Order (V1)

```text
1. Repo scaffolding, frozen contracts imported, fixture pipeline
2. Detection model (real public labeled dataset) + deterministic anomaly tagging
3. Seed fixtures (customers, accounts, cards, devices, merchants) incl.
   the branching-proof and merchant-risk-trend scenarios
4. Evidence tools + minimum-evidence floor + bounded Evidence Agent
5. Gemini reasoning + citation validation + Decision Robustness Scorer
6. Policy rules + Firestore case store + full pipeline wiring
7. Analyst UI (queue + case detail) + evaluation numbers
8. Demo hardening + submission package
```

---

# 34. Explicit Build / Don't-Build Boundary (V1)

## Build

- single Cloud Run service, in-process modules, synchronous pipeline
- real detector model trained/evaluated on a public labeled dataset
- deterministic anomaly tagging (5 V1 tags, `KYC_ANOMALY` optional)
- seeded fixture data, including the branching-proof and merchant-risk-trend scenarios
- six read-only evidence tools, incl. the v1.1 `get_merchant_risk` shape
- genuinely agentic, bounded Evidence Agent (max 6 calls, floor-enforced)
- Gemini Pro structured reasoning with schema + citation validation and reprompt-then-escalate
- Decision Robustness Scorer (fast-path + live counterfactual)
- deterministic versioned Policy (6 rules, `AUTO_RESOLVE`/`ESCALATE` only)
- Firestore live case store + `audit_events` subcollection
- analyst UI: queue + case detail, `CLEAR / BLOCK_HOLD / ESCALATE_SENIOR`
- offline evaluation numbers (detection, Evidence Agent, reasoning, end-to-end)
- rehearsed live-demo counterfactual with a tested, pre-cached fallback

## Do not build (V1)

- other payment rails (UPI, IMPS/NEFT/RTGS, ATM, incoming-side fraud)
- `IMPOSSIBLE_TRAVEL` / `UNUSUAL_TIME` anomaly tags
- RAG / precedent retrieval / Vertex AI Vector Search
- BigQuery
- Pub/Sub event backbone, DLQs, scheduled sweeps
- multi-service topology or per-service service accounts
- a standalone synthetic transaction generator service
- graph database
- real KYC/merchant API integrations
- custom fine-tuned Gemini or custom GNN
- autonomous policy learning
- multi-tenant SaaS
- a fairness pipeline
- a chat interface as the primary analyst surface

---

# 35. Final Authority Model

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
  | BLOCK_HOLD may be recommended, advisory only
  v
Decision Robustness Scorer
  |
  | ROBUST / FRAGILE (investigative signal only — not a Policy input)
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

```text
SYSTEM ESCALATION  = ESCALATE
HUMAN ESCALATION   = ESCALATE_SENIOR
HUMAN BLOCK        = BLOCK_HOLD
AUTOMATED BLOCK    = NOT ALLOWED
```

---

# 36. Freeze Statement

**Sentinel Technical Design & Contracts v1.2 is frozen for V1 implementation**
and is in sync with V1 Build Architecture v1.1 and the V1 Build Checklist.

No implementation may introduce an automated `BLOCK_HOLD` path, `AUTO_DECLINE`,
or any equivalent automated blocking behavior. No implementation may introduce
Pub/Sub, BigQuery, Vector Search/RAG, or a multi-service topology in V1 — these
remain named, deliberate post-V1 extensions (see architecture v1.1 §9), not
things a builder should reach for under schedule pressure.

Any future change to the safety boundaries in §2, §19–22, or §32 requires an
explicit architecture review and contract-version change.
