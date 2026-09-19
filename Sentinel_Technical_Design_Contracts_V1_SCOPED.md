# Sentinel — Technical Design & Contracts (V1-Scoped)
## FINAL CONTRACT FREEZE — v1.3

**Status:** FROZEN
**Supersedes:** Technical Design & Contracts v1.2 FINAL FROZEN
**Scope:** Contract layer for the V1 prototype only — one Cloud Run service, Firestore only, no Pub/Sub, no BigQuery, no RAG/Vector Search
**Paired documents (must stay in sync):** `Sentinel_V1_Build_Architecture_v1.1.md`, `Sentinel_V1_Build_Checklist.pdf`
**Freeze gate:** Must be accepted before Phase 4 (Policy) implementation, per the V1 Build Checklist. v1.3 is a narrow, reviewed amendment to Rule P-004 only (§0.1) — it does not reopen the Phase 4 gate for any other rule or section.

---

# 0. Change Log — what changed from v1.1 FINAL FROZEN and why

| Change | Reason |
|---|---|
| Removed Pub/Sub, event envelope, topics, DLQ, scheduled sweep | V1 architecture is a single Cloud Run service with synchronous, in-process calls. These are real, named V2 upgrades (see §35) — they do not exist in V1 and must not appear in the frozen V1 contract. |
| Removed BigQuery as a data store | V1 uses Firestore only, including for the audit trail (`audit_events` subcollection). BigQuery is a named V2 upgrade. |
| Removed RAG / Vertex AI Vector Search / Precedent Contract | V1 Reasoning does not retrieve precedents. RAG is deliberately deferred (see the V1 Build Architecture §6) and only added back if it clears a specific bar — it is not part of the frozen V1 contract. |
| Removed the dedicated Recent-Anomaly Cache (`recent_anomalies/{account_id}`) as a standalone Firestore collection | V1's branching-proof scenario gets linked-account correlation directly from `get_linked_entities` fixture data. A separate TTL cache is a real V2 concern (order-independent correlation across flagged cases) that doesn't exist in the single-scenario V1 build. |
| Rewrote Service API Boundaries and Service Account Boundaries | The original document defined five separately deployed services with five separate service accounts. V1 is one Cloud Run service with one service account and in-process module calls, not HTTP hops between services. |
| Updated `Transaction` contract | Added `payment_rail`, `direction`, `authorization_stage`, `card_id`, `card_present`; removed the generic `transaction_type` field. Aligns with the domain-scoped V1.1 architecture (CNP card, outgoing, pre-authorization). |
| Updated `get_merchant_risk()` | Replaced the placeholder shape (`merchant_risk_band`, `risk_reasons`) with the real investigable shape (`recent_fraud_report_count`, `fraud_report_trend`, `customer_prior_transactions_with_merchant`) already defined in the V1.1 architecture. The two documents previously disagreed on this tool's contract — this was a real bug, not a style issue. |
| Pruned `anomaly_tags` to the V1 CNP-relevant set | Dropped `IMPOSSIBLE_TRAVEL` and `UNUSUAL_TIME` (not modeled in V1 fixtures). `KYC_ANOMALY` retained as optional/stretch only, matching the V1 Build Checklist. |
| **Added `HARD_RISK_TAGS` as an explicit, named constant** | The auto-resolve rule previously said "no hard-risk-tag" without ever defining which tags qualify. This was a genuine ambiguity — two engineers could implement two different behaviors from the same rule text. See §6.3 and §18, Rule P-004. |
| Rewrote Implementation Order | Now identical in sequence to the V1 Build Checklist's Phase 0–6, instead of a separate 18-step list that included V2 items. |
| Split the Build/Don't-Build boundary into three lists | **Build (V1)**, **Deferred (named V2 upgrades, not rejected)**, **Don't Build (rejected for any version of this hackathon submission)** — the original document blurred "not now" and "not ever" into one list. |

Everything not listed above is unchanged: the authority model, all safety invariants, the Evidence Agent's bounded-loop constraints, the Policy engine's `AUTO_RESOLVE | ESCALATE`-only output, the human decision contract, and `ESCALATE_SENIOR` naming.

---

# 0.1 Change Log — v1.3 amendment (what changed from v1.2 and why)

**Amendment scope:** Rule P-004 only (§16), and its supporting explanation in §6.3. No other rule, contract, or safety invariant is altered by this amendment.

| Change | Reason |
|---|---|
| **Amended Rule P-004's auto-resolve condition** from `(anomaly_tags[] ∩ HARD_RISK_TAGS) = ∅` to `anomaly_tags[] = []` | Product/policy review identified a semantic conflation between two distinct concepts: **RISK** (how risky `risk_score`/`risk_band` judges the transaction to be) and **CLEAN** (whether Sentinel detected zero anomaly signals of any kind). Under v1.2, a transaction could carry a statistical anomaly tag (`NEW_DEVICE`, `UNUSUAL_LOCATION`, `UNUSUAL_AMOUNT`) and still auto-resolve solely because `risk_score` happened to be LOW — silently communicating "LOW risk = automatically safe." Those are not the same claim: a risk signal is still a signal, and a LOW-risk transaction that Sentinel flagged as anomalous is not the same thing as a transaction Sentinel found nothing wrong with. v1.3 makes `AUTO_RESOLVE` mean "LOW risk **and** clean (zero anomaly tags) **and** complete evidence **and** non-HIGH findings," narrowing the automated-resolution surface so that any detected anomaly — statistical or structural — now routes to human review via Rule P-005 (Otherwise), never silently auto-resolves. |
| **Bumped Policy `RULE_SET_VERSION` from `1.0.0` to `1.1.0`** | Rule P-004's condition text changed. Safety Invariant 7 (§30) requires every `PolicyDecision` to record `rule_id` + `rule_version`; bumping the shared rule-set version ensures a decision made under the old (narrower) auto-resolve gate remains distinguishable in Firestore from a decision made under this amendment, even though `rule_id` is unchanged (`P-004`). Rules P-001/P-002/P-003/P-005 are textually unchanged but share the same rule-set version field, so their recorded `rule_version` also advances to `1.1.0` from this point forward — this reflects when the decision was made, not that their conditions changed. |

**Previous P-004 behavior (v1.2):** a LOW-risk, evidence-complete transaction could auto-resolve as long as no *structural* (`HARD_RISK_TAGS`) tag was present — a statistical tag alone (`NEW_DEVICE`, `UNUSUAL_LOCATION`, `UNUSUAL_AMOUNT`) did not block auto-resolve.

**New P-004 behavior (v1.3):** a transaction auto-resolves only if it is LOW risk **and** carries zero anomaly tags of any kind **and** evidence is complete **and** `findings.risk_assessment != HIGH`. Any anomaly tag — statistical or structural — now forces the case through to Rule P-005 (Otherwise) → `ESCALATE` (human review). This intentionally narrows the `AUTO_RESOLVE` surface; it can only move cases from `AUTO_RESOLVE` to `ESCALATE`, never the reverse (verified: `HARD_RISK_TAGS` members were already excluded from auto-resolve under v1.2, so they remain excluded under the strictly stricter v1.3 condition — Safety Invariant 6 is preserved unchanged).

Everything not listed above is unchanged: `HARD_RISK_TAGS` (§6.3) and its membership, Rules P-001/P-002/P-003/P-005 (conditions and priorities), the `PolicyOutcome` enum (`AUTO_RESOLVE | ESCALATE` only, still no `BLOCK_HOLD`/`AUTO_DECLINE` path), all 10 Safety Invariants (§30), the Human Decision Contract (§18), the Evidence Agent, Gemini Reasoning, Robustness scoring, detection thresholds, authentication/roles, the Firestore schema, and the 4-endpoint API surface (§23.1).

---

# 1. Purpose

This document is the canonical contract between Sentinel's internal modules, evidence tools, Firestore, and the analyst UI, for the **V1 prototype** — one deployable Cloud Run service.

It converts the frozen V1 architecture into implementation-level contracts so that individual modules can be built and tested independently without changing safety boundaries, even though they run in-process rather than as separate services.

The governing safety principle is:

> **Probabilistic AI investigates and reasons. Deterministic policy controls automated disposition. Humans retain authority over blocking and overrides.**

The most important authority guarantee is:

> **There is no automated BLOCK_HOLD and no AUTO_DECLINE. Only a human analyst may execute BLOCK_HOLD.**

---

# 2. Contract Principles

## 2.1 AI is advisory; Policy is deterministic

Gemini may investigate evidence, identify supporting and counter factors, assess risk categorically, and recommend a disposition.

Gemini may not clear a transaction, block or hold a transaction, move money, modify policy rules, or invoke mutating tools.

## 2.2 Policy is the sole automated action authority

The deterministic Policy engine may produce only:

```text
AUTO_RESOLVE
ESCALATE
```

It may never produce `BLOCK_HOLD`. `BLOCK_HOLD` is exclusively a human analyst action.

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

Every detection, evidence bundle, model output, policy decision, and human action carries version/provenance information, and every record carries `case_id` and `transaction_id`.

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
audit_event_id
```

`transaction_id` and `case_id` are propagated through every function call and every structured log line across the whole request lifecycle — this is V1's substitute for a distributed trace ID, since there is no event bus to carry a correlation ID between services.

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

# 4. Transaction Contract

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

  payment_rail: CARD_CNP
  direction: OUTGOING
  authorization_stage: PRE_AUTH | AUTH | SETTLED

  device_id: string
  ip_address: string
  geo: {
    lat: decimal
    lon: decimal
    country: string
  }

  channel: WEB | MOBILE
  merchant_category: string
  card_present: boolean
}
```

### Contract rules

- `transaction_id` is globally unique.
- The transaction is immutable after ingestion.
- A transaction may have at most one active investigation case.
- Duplicate case creation for the same `transaction_id` must be rejected or merged.
- `payment_rail` is an enum with one value populated in V1 (`CARD_CNP`); this is the extension point for additional rails in a later version, without changing the pipeline shape.
- V1 operates exclusively at `authorization_stage = PRE_AUTH`. This is what gives `ESCALATE` real operational meaning: holding the authorization, not filing a retrospective report.

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

State transitions are controlled by the module responsible for the corresponding stage, running in-process within the single Cloud Run service. No model output may directly transition a case to `AUTO_RESOLVED`, `ESCALATED`, or `FINALIZED`.

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

`risk_score` is the measurable detector signal, produced by a real model trained and evaluated on real labeled data. It is the numeric signal used for calibrated detector evaluation. Gemini's `risk_assessment` must never be treated as a calibrated probability.

## 6.2 Deterministic anomaly tagging (V1 scope)

`anomaly_tags[]` are produced by a deterministic post-processing step from transaction/customer/context features. They are not a hidden second AI model.

**V1 allowed tags (CNP-relevant only):**

```text
NEW_DEVICE
UNUSUAL_LOCATION
UNUSUAL_AMOUNT
MERCHANT_RISK
LINKED_ENTITY_ANOMALY
```

`KYC_ANOMALY` is optional/stretch, only if `get_mock_kyc_status` is implemented. `IMPOSSIBLE_TRAVEL` and `UNUSUAL_TIME` are out of scope for V1 — no fixture data models them, and adding the tags without corresponding evidence would create an untestable rule path.

## 6.3 Hard-risk tags, clean transactions, and the v1.3 auto-resolve requirement

Anomaly tags are split into two categories, based on whether the signal is something `risk_score` structurally can already see.

**Statistical tags** — deviations from the customer's *own* baseline. These are exactly the kind of feature `risk_score` is trained on:

```text
NEW_DEVICE
UNUSUAL_LOCATION
UNUSUAL_AMOUNT
```

**Structural tags** — evidence about something a single per-transaction score cannot see by construction: a third party's risk profile, or cross-account correlation. A low `risk_score` says "this transaction wasn't unusual for this customer" — it says nothing about whether the merchant is currently compromised or whether this device just appeared on another account. These get a categorical veto over auto-resolve, defined as a named constant:

```text
HARD_RISK_TAGS: AnomalyTag[] = [
  MERCHANT_RISK,
  LINKED_ENTITY_ANOMALY,
  KYC_ANOMALY
]
```

`HARD_RISK_TAGS` is referenced by name in Policy Rule P-004 (§18) — it must not be reimplemented as an inline literal in Policy code; both must reference this single defined constant so the two never drift out of sync. `HARD_RISK_TAGS` remains the categorical, risk-score-independent structural veto described by Safety Invariant 6 (§30): a transaction carrying any structural tag can never auto-resolve, regardless of `risk_score` — this is unchanged by the v1.3 amendment below.

### RISK vs. ANOMALY vs. CLEAN vs. DISPOSITION (v1.3)

`risk_score`/`risk_band` and `anomaly_tags[]` answer two different questions, and Rule P-004 (§16) must not conflate them:

- **RISK** — how risky does `risk_score` judge this transaction to be (`LOW`/`MEDIUM`/`HIGH`)? A statistical tag such as `NEW_DEVICE` is already one of the features `risk_score` was computed from, so it is legitimately possible for a transaction carrying a statistical tag to still score `LOW` overall.
- **ANOMALY** — did Sentinel's deterministic tagging step detect *any* deviation worth naming, statistical or structural?
- **CLEAN** — the absence of anomaly: `anomaly_tags[] = []`.
- **DISPOSITION** — what Policy does about it.

Prior to v1.3, Rule P-004 treated "`risk_band` = LOW" as sufficient grounds for `AUTO_RESOLVE` as long as no *structural* tag was present, which meant `LOW` + a statistical tag (e.g. `NEW_DEVICE`) could still auto-resolve. This conflated **LOW risk** with **CLEAN**, which are not the same claim: `risk_score` having already priced a statistical signal into its *risk level* does not mean that signal should be silently waved through at the *disposition* stage. As of v1.3, Rule P-004 additionally requires the transaction to be **CLEAN** (`anomaly_tags[] = []`) before it is eligible for `AUTO_RESOLVE` — see the amended condition in §16. A transaction that is `LOW` risk but carries any anomaly tag (statistical or structural) is therefore **not** auto-resolve-eligible and is routed to human review via Rule P-005 (Otherwise).

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

The agent's own judgment may request additional evidence beyond the floor, but it cannot bypass the floor.

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

- is genuinely agentic — its tool sequence must be able to change based on what a prior tool call revealed, not solely on the initial `anomaly_tags[]`,
- may dynamically select the next relevant read-only tool,
- may react to facts discovered by previous tools,
- has a maximum of 6 tool calls,
- has a total execution deadline,
- has per-tool timeouts,
- uses an explicit tool allow-list,
- cannot call mutating tools,
- cannot change Policy rules,
- has no hidden cross-case memory,
- uses Gemini Flash (cost/latency-appropriate for a high-frequency, per-call-simple decision).

## 9.4 Minimum evidence floor (V1 scope)

```text
NEW_DEVICE
  -> get_device_history

UNUSUAL_LOCATION
  -> get_ip_geovelocity

UNUSUAL_AMOUNT
  -> get_behavioral_baseline

MERCHANT_RISK
  -> get_merchant_risk

LINKED_ENTITY_ANOMALY
  -> get_linked_entities

KYC_ANOMALY (optional/stretch)
  -> get_mock_kyc_status
```

For combinations, the union of required tools is the minimum floor.

---

# 10. Evidence Tool Contracts

All Evidence Agent tools are read-only, mocked against seeded fixture data for V1.

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

This is the tool whose fixture-seeded output (a device also seen on a different account) drives the branching-proof scenario — see the V1 Build Architecture §5.

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

`recent_anomalies` here is populated directly from seeded fixture data for V1's specific demo scenarios. There is no standalone TTL cache module in V1 — see §0 change log.

## 10.5 get_merchant_risk — updated shape (was out of sync with the domain-scoped architecture)

```text
Input:
  merchant_id
  customer_id

Output:
  category: string
  onboarding_date: date
  chargeback_rate: decimal
  recent_fraud_report_count: integer
  fraud_report_trend: RISING | STABLE | FALLING
  customer_prior_transactions_with_merchant: integer
  risk_band: LOW | MEDIUM | HIGH
  source_record_ids: string[]
```

This is genuinely investigable evidence, not a static label — `fraud_report_trend` in particular is what a real fraud investigator would weigh, and it's what the Evidence Agent and Reasoning should be reasoning over for the `MERCHANT_RISK` tag.

## 10.6 get_mock_kyc_status (optional/stretch for V1)

```text
Input:
  customer_id

Output:
  kyc_status: VERIFIED | REVIEW | FAILED
  kyc_flags: string[]
  source_record_ids: string[]
```

---

# 11. Tool Failure Semantics

If a tool fails:

1. Retry up to the bounded retry limit.
2. Continue with remaining safe tools where possible.
3. Mark unavailable evidence explicitly.
4. Produce `PARTIAL` evidence if the minimum floor cannot be satisfied.
5. Policy must escalate partial-evidence cases (Rule P-001, §18).

A degraded system escalates more cases rather than silently auto-resolving uncertain ones.

---

# 12. Gemini Reasoning Contract

The Reasoning component is a **Gemini reasoning service**, not a second autonomous tool-selection agent — it does not make retrieval decisions in V1 (no RAG). It receives a completed/partial `EvidenceBundle` and produces structured findings.

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

Uses Gemini Pro (higher reasoning load, lower call volume than the Evidence Agent's loop).

## 12.1 Critical safety clarification

`recommended_disposition = BLOCK_HOLD` is **advisory only**. Gemini may recommend it for an analyst to consider, but:

- Gemini cannot execute it.
- Policy cannot execute it.
- No automated module can execute it.
- Only a human analyst may execute `BLOCK_HOLD`.

## 12.2 Gemini uncertainty

Gemini's categorical `risk_assessment` is used as a structured reasoning signal that can only *tighten* Policy's escalation threshold, never loosen it (Rule P-002, §18). Any displayed Gemini confidence is informational only and is never a calibrated probability or the sole basis for an automated action.

---

# 13. Finding Factor Contract

```text
FindingFactor {
  statement: string
  fact_ids: string[]
  materiality: HIGH | MEDIUM | LOW
}
```

`materiality` is also the input to the Decision Robustness Scorer's fast-path estimate — see the V1 Build Architecture §3.5.

---

# 14. Citation Contract

```text
Citation {
  claim_id: string
  fact_ids: string[]
}
```

Citation validation in V1 guarantees **structural groundedness**: the citation exists, the referenced fact exists, and the referenced ID is valid. It does not claim full semantic verification that the cited evidence necessarily supports every wording nuance of the claim — a stronger second-pass semantic verifier is a named V2 improvement.

*(No `precedent_ids` field — V1 has no RAG. See §0 change log and §35.)*

---

# 15. Policy Rule Contract

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

## 15.1 Non-negotiable authority boundary

The `PolicyRule.outcome` enum is intentionally limited to `AUTO_RESOLVE | ESCALATE`. It does **not** contain `BLOCK_HOLD`. A policy rule cannot be authored to automatically block/hold a transaction — this must be verifiable by a plain code search for the literal string `BLOCK_HOLD` outside the human-decision contract.

---

# 16. Mandatory Policy Rules

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

Deliberately included so Gemini's structured risk assessment measurably affects deterministic behavior — in the escalation-only direction — without giving Gemini action authority.

## Rule P-003 — High-value transactions

```text
IF risk_score >= HIGH
AND amount >= HIGH_VALUE_THRESHOLD
AND evidence.completeness = COMPLETE
    -> ESCALATE
```

`HIGH_VALUE_THRESHOLD` is an evaluation-tuned parameter, selected from the held-out evaluation set using an explicit precision/recall or cost-of-error tradeoff, and recorded with the rule version.

## Rule P-004 — Clean, low-risk eligible cases (auto-resolve) — amended in v1.3

```text
IF risk_score <= LOW
AND evidence.completeness = COMPLETE
AND anomaly_tags[] = []
AND findings.risk_assessment != HIGH
    -> AUTO_RESOLVE
```

**v1.3 amendment (§0.1):** the condition now requires `anomaly_tags[] = []` — zero anomaly tags of any kind — rather than merely the absence of a `HARD_RISK_TAGS` member. A transaction carrying *any* anomaly tag, statistical (`NEW_DEVICE`, `UNUSUAL_LOCATION`, `UNUSUAL_AMOUNT`) or structural (`MERCHANT_RISK`, `LINKED_ENTITY_ANOMALY`, `KYC_ANOMALY`, i.e. `HARD_RISK_TAGS` as defined in §6.3), is no longer eligible for auto-resolve, regardless of `risk_score`. `LOW` risk no longer implies `AUTO_RESOLVE`; it is a necessary condition, not a sufficient one — see §6.3's RISK vs. ANOMALY vs. CLEAN vs. DISPOSITION distinction. Only a transaction that is both `LOW` risk **and** anomaly-free (`CLEAN`) — with complete evidence and non-HIGH findings — auto-resolves. Any other LOW-risk transaction, and every MEDIUM/HIGH-risk transaction, falls through to Rule P-005 (Otherwise) → `ESCALATE` (human review), unless an earlier rule (P-001/P-002/P-003) already matched it.

## Otherwise

```text
OTHERWISE -> ESCALATE
```

No rule may produce `BLOCK_HOLD`.

---

# 17. Policy Decision Contract

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

`AUTO_RESOLVE` means: release the pre-authorization to proceed normally. `ESCALATE` means: **hold the authorization** pending analyst review — the transaction does not settle until a human acts.

---

# 18. Human Decision Contract

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

## 18.1 Human authority

Only a human analyst may execute `BLOCK_HOLD`. `ESCALATE_SENIOR` is explicitly an analyst action, distinct from the system-level case state `ESCALATED` — these must never be conflated in the UI or the audit trail.

## 18.2 Analyst acknowledgement

The analyst must acknowledge at least one evidence factor before a final action is enabled in the UI, so the human-in-the-loop is substantive rather than ceremonial.

---

# 19. Execution Model (V1 — in-process, no event bus)

V1 has **no Pub/Sub, no event envelope, no topics.** All stages run as synchronous, in-process function calls within one Cloud Run service, triggered by a single external request:

```text
POST /transactions
  -> Detection()
  -> (if flagged) EvidenceAgent()
  -> Reasoning()
  -> RobustnessScorer()
  -> Policy()
  -> Firestore write
```

`case_id` and `transaction_id` are threaded through every function call and every structured log line — this is V1's traceability mechanism, in place of the event-envelope correlation ID a Pub/Sub-based version would use.

---

# 20. Idempotency Contract

## Request-level idempotency

A duplicate `POST /transactions` for a `transaction_id` that already has an active case must not create a second independent investigation — the implementation must reject, return, or merge into the existing case.

## Decision-level idempotency

A policy decision is uniquely associated with one case evaluation. Human decisions must not be applied twice for the same human action request (e.g. a double-submitted UI action).

---

# 21. Audit Contract

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
}
```

V1 stores audit events as a Firestore `audit_events` subcollection under each `cases/{case_id}` document — a restricted, append-oriented collection, written on every state transition. Do not describe this as WORM/cryptographically immutable; it isn't, and shouldn't be claimed as such.

---

# 22. Error Contract

```text
ErrorEnvelope {
  error_code: string
  message: string
  retryable: boolean
  case_id?: string
  transaction_id?: string
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

Firestore write failure
    -> bounded client retry
    -> pause rather than proceed with unsaved state

Unhandled exception at any pipeline stage
    -> abort the request
    -> mark the case ESCALATED with an audit note
    -> return a clear error to the caller
```

The invariant is:

> **When in doubt, Sentinel does less, not more.**

*(There is no DLQ or scheduled sweep in V1 — those are Pub/Sub-dependent concepts that don't apply to a synchronous in-process pipeline. See §35 for the named V2 upgrade.)*

---

# 23. Service Boundaries (V1 — one Cloud Run service)

V1 exposes four external HTTP endpoints from a single deployed service. Everything else is an internal function call, not a network hop.

## 23.1 External API

```text
POST /transactions                      -> full pipeline entry (Detection through Policy)
GET  /cases                              -> queue view (escalated cases)
GET  /cases/{case_id}                    -> case detail
POST /cases/{case_id}/decision           -> human decision (CLEAR | BLOCK_HOLD | ESCALATE_SENIOR)
```

## 23.2 Internal modules (in-process function calls, not HTTP)

```text
Detection(transaction) -> DetectionOutput
EvidenceAgent(transaction, detection) -> EvidenceAgentOutput
Reasoning(evidence_bundle) -> CaseFindings
RobustnessScorer(findings, evidence_bundle) -> RobustnessResult
Policy(detection, evidence_bundle, findings) -> PolicyDecision
```

Only `POST /cases/{case_id}/decision` may execute `BLOCK_HOLD`.

---

# 24. Service Account Boundary (V1 — one service account)

V1 is one Cloud Run deployment, so there is one service account, `sentinel-v1-sa`, with least-privilege roles: Vertex AI User (for Gemini calls) and Firestore User (read/write on the `cases` collection and its subcollections only — not project-wide). It may not be granted Owner/Editor.

The analyst identity for `/cases/{case_id}/decision` is authenticated and authorized separately from the service account — only an authenticated analyst session can finalize `BLOCK_HOLD`.

---

# 25. Data Responsibilities (V1 — Firestore only)

## Firestore

Use for everything in V1:
- live case state (`cases/{case_id}`),
- the analyst queue,
- the audit trail (`audit_events` subcollection),
- fixture/seed reference data.

## Local evaluation artifacts

Evaluation numbers (precision/recall/AUC, citation-validity rate, branching-scenario success rate) are computed against held-out data and saved to `eval/results_summary.md` in the repository — not to any live database. This is intentional: eval is a build-time artifact for the submission, not a runtime service in V1.

*(BigQuery, Cloud Storage, and Vertex AI Vector Search are not used in V1. See §35.)*

---

# 26. Query Requirements (V1 — Firestore only)

Primary access patterns:

```text
case_id lookup
open cases by state
cases assigned to analyst
```

Required indexes should be created only for these actual query patterns — do not pre-build indexes for queries V1 doesn't run.

---

# 27. Local Development Topology (V1)

```text
Transaction Generator (seeded fixtures)
   |
   v
POST /transactions (single Cloud Run service, or local dev server)
   |
   +-- Detection
   +-- Evidence Agent  --> mocked tools (fixture data)
   +-- Reasoning  --> Gemini Pro
   +-- Robustness Scorer
   +-- Policy
   |
   v
Firestore (or Firestore emulator locally)
   |
   v
Analyst UI
```

No Pub/Sub emulator, no BigQuery, no Vector Search in this topology — local dev mirrors production exactly, which is one of the practical benefits of the single-service V1 design.

---

# 28. Observability Contract (V1)

Every log line carries `case_id` and `transaction_id`. Track at minimum:

```text
end-to-end latency
per-stage latency (Detection, Evidence Agent, Reasoning, Policy)
detector flag rate
Evidence Agent tool-call count and branching-scenario success rate
evidence completeness rate
Gemini failures
schema-validation failures
citation-validation failures
policy outcomes (AUTO_RESOLVE vs. ESCALATE, and which rule fired)
escalation rate
human decision latency
```

*(No DLQ count or stuck-case count — these are Pub/Sub-dependent metrics that don't apply to V1's synchronous pipeline.)*

---

# 29. Evaluation Contract

The evaluation harness must measure separately, exactly as specified in the V1 Build Checklist Phase 5.5:

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
branching-scenario success rate (repeated runs)
tool-call count
latency
```

## Reasoning
```text
structured-output validity
citation validity
structural groundedness
```

## End-to-end
```text
decision accuracy against hand-labeled seeded scenarios
escalation accuracy
latency
```

Thresholds (e.g. `HIGH_VALUE_THRESHOLD` in Rule P-003) must be selected using held-out evaluation data, not arbitrary demo intuition.

---

# 30. Safety Invariants — FINAL

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
A transaction carrying any HARD_RISK_TAGS member cannot auto-resolve, regardless of risk_score.
```

### Invariant 7
```text
Every automated Policy decision records rule_id + rule_version.
```

### Invariant 8
```text
Every material reasoning factor is traceable to evidence (fact_id).
```

### Invariant 9
```text
A duplicate request for an already-open transaction_id cannot create a second independent case.
```

### Invariant 10
```text
An unhandled failure at any pipeline stage results in ESCALATED, never a silent AUTO_RESOLVED.
```

---

# 31. Implementation Order (matches the V1 Build Checklist exactly)

```text
Phase 0 — Accounts, repo, domain scope lock-in
Phase 1 — Real labeled dataset, Detection model, deterministic anomaly tagging, fixture/seed data
Phase 2 — Evidence tools, minimum-evidence floor, bounded Gemini loop, branching-proof scenario
Phase 3 — Gemini Reasoning, citation validation, Decision Robustness Scorer
Phase 4 — Policy engine (including HARD_RISK_TAGS), Firestore case store, full pipeline wiring
Phase 5 — Analyst UI, evaluation numbers
Phase 6 — Demo hardening, fallback path, submission
```

Policy (Phase 4) must not begin until this contract, including §6.3 and Rule P-004, is accepted.

---

# 32. Explicit Scope Boundary

## Build (V1)

- synthetic transaction generator with seeded, replayable fraud scenarios,
- real detector model on real public labeled data,
- deterministic anomaly tagging, including `HARD_RISK_TAGS`,
- genuine bounded Evidence Agent with a provable branching scenario,
- six read-only evidence tools (five required, KYC optional),
- Gemini structured reasoning with citation validation,
- Decision Robustness Scorer,
- deterministic versioned Policy,
- Firestore live case queue and audit trail,
- analyst UI with `CLEAR / BLOCK_HOLD / ESCALATE_SENIOR`,
- structured logging and the observability metrics in §28,
- offline evaluation against held-out data,
- the signal-removal / robustness demonstration with a rehearsed fallback.

## Deferred (named V2 upgrades — not rejected, not built now)

- Pub/Sub event backbone, DLQs, scheduled fail-safe sweep,
- BigQuery for historical/audit/evaluation data at scale,
- RAG precedent retrieval via Vertex AI Vector Search,
- a dedicated short-TTL recent-anomaly cache for order-independent cross-case correlation,
- additional payment rails beyond CNP card (bank transfer, UPI),
- independently scaled multi-service deployment.

## Do not build (rejected for any version of this submission)

- graph database,
- real KYC/merchant API integrations,
- custom fine-tuned Gemini,
- custom GNN,
- autonomous/unsupervised policy learning,
- multi-tenant SaaS,
- half-built fairness pipeline,
- chat interface as the primary analyst surface.

---

# 33. Final Authority Model

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
  +--> AUTO_RESOLVE   (only if no HARD_RISK_TAGS present, evidence complete, risk low)
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
SYSTEM ESCALATION   = ESCALATE
HUMAN ESCALATION    = ESCALATE_SENIOR
HUMAN BLOCK         = BLOCK_HOLD
AUTOMATED BLOCK      = NOT ALLOWED, at any risk_score, for any HARD_RISK_TAGS member
```

---

# 34. Freeze Statement

**Sentinel Technical Design & Contracts, V1-Scoped, v1.3, is frozen for implementation.**

This document, the V1 Build Architecture (v1.1), and the V1 Build Checklist now describe the same system, with no infrastructure or schema disagreement between them. No implementation may introduce an automated `BLOCK_HOLD` path, `AUTO_DECLINE`, or any equivalent automated blocking behavior. No implementation may introduce Pub/Sub, BigQuery, or RAG into the V1 build — these are named, deliberate V2 upgrades, not omissions.

Any future change to these safety boundaries, or any promotion of a deferred item into V1 scope, requires an explicit review and a contract-version change.

**v1.3 note:** this revision is a narrow, reviewed amendment to Rule P-004's auto-resolve condition and its §6.3 explanation only (see §0.1) — reviewed and approved specifically because it strictly narrows the `AUTO_RESOLVE` surface and leaves all 10 Safety Invariants (§30), `HARD_RISK_TAGS`, Rules P-001/P-002/P-003/P-005, and every other section of this contract unchanged. It does not reopen the Phase 4 gate for any other component.

**Next step (unchanged): Phase 4 (Policy) implementation, gated on this frozen contract, in particular §6.3 and Rule P-004.**
