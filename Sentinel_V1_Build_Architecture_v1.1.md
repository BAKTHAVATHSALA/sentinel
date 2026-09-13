# SENTINEL — V1 Build Architecture (v1.1 — Domain-Scoped)
## The smallest system that can genuinely win

**Supersedes:** V1 Build Architecture (original). This version resolves the business/domain ambiguity your manager flagged. Nothing structural changed — the pipeline, the one-service design, the branching agent, and the Decision Robustness Scorer all survive unchanged. What changed: the transaction is now a specific, real BFSI scenario instead of a generic envelope, and `get_merchant_risk()` now returns real investigable evidence instead of a placeholder label.

---

## 0. Change Log — what's different from V1.0 and why

| Change | Reason |
|---|---|
| `Transaction` gains `payment_rail`, `direction`, `authorization_stage` as required fields | The original schema silently assumed card payments without ever saying so — unbuildable ambiguity a manager or judge would catch immediately |
| `get_merchant_risk()` output expanded with `recent_fraud_report_count`, `fraud_report_trend`, `customer_prior_transactions_with_merchant` | The old shape (`category`, `risk_band`, `prior_flags[]`) was a static label, not evidence an investigator could actually reason over |
| Domain entities section added (Customer, Account, Card, Merchant, Device, IP/Location) with concrete fields | Previously implicit and unstated; now explicit enough to code against |
| Policy semantics clarified: `ESCALATE` now means "hold the authorization," not a retrospective flag | Only meaningful because the lifecycle stage (pre-authorization) is now defined — this was undefined before |
| Demo scenario updated to the CNP e-commerce case with a merchant-risk-trend evidence thread alongside the device-linkage thread | Strengthens the Robustness Scorer demo — now two independently weighable signals instead of one |

Everything else — the single Cloud Run service, in-process modules, Firestore-only storage, no Pub/Sub/BigQuery/RAG in V1, the build order, the exit checklist — is unchanged and still correct. This is a domain-definition fix, not a redesign.

---

## 1. Domain Scope — resolved

**Scenario: card-not-present (CNP) e-commerce purchase, outgoing, pre-authorization.**

This is the one rail where every evidence tool already in the design (device, IP/geo, behavioral baseline, merchant) is natively meaningful with no schema rework, and where "ESCALATE" has real operational teeth — the transaction hasn't settled yet, so escalation means holding the authorization pending human review, not filing a retrospective report.

**Explicitly out of scope for V1** (name these if asked, don't build them): UPI/real-time peer transfers, IMPS/NEFT/RTGS bank transfers, ATM withdrawals, incoming/receiving-side fraud (e.g. mule-account detection). Each has a genuinely different evidence model — CNP card is the correct starting rail, and the path to add rails later is to extend `payment_rail` as an enum and add rail-specific evidence tools, not to rebuild the pipeline.

---

## 2. Domain Model — entities

| Entity | Key fields | Notes |
|---|---|---|
| **Customer** | `customer_id`, `tenure_months`, `kyc_status` | Existing customer, 18+ months tenure for the V1 fixture — an established behavioral baseline exists |
| **Account** | `account_id`, `customer_id`, `status`, `linked_account_ids[]` | Single checking/credit account; linked accounts exist in the fixture data for the branching scenario, not flagged at the start |
| **Card / Payment Instrument** | `card_id`, `account_id`, `issued_at`, `card_present: boolean` | `card_present = false` for the V1 scenario — this field is what actually encodes "CNP" at the data level |
| **Merchant** | `merchant_id`, `category`, `onboarding_date`, `chargeback_rate`, `recent_fraud_reports[]`, `risk_band` | New-to-this-customer merchant; fraud-report history is seeded and must be *retrieved*, not assumed |
| **Device** | `device_id`, `first_seen`, `linked_customer_ids[]` | New device for this transaction, first seen ~40 minutes prior in the fixture |
| **IP / Location** | `ip_address`, `geo`, `asn`, `first_seen` | Location inconsistent with the customer's established pattern — unusual, not impossible-travel |

These extend, not replace, the existing `Fact`/`EvidenceBundle`/`CaseFindings`/`PolicyDecision`/`AuditEvent` contracts from the earlier design — none of those need changes.

---

## 3. Transaction Contract — updated

```text
Transaction {
  transaction_id: string
  customer_id: string
  account_id: string
  card_id: string
  merchant_id: string

  amount: decimal
  currency: string
  timestamp: datetime_utc

  payment_rail: CARD_CNP                       # NEW — enum, extensible later
  direction: OUTGOING                            # NEW — explicit, was previously unstated
  authorization_stage: PRE_AUTH | AUTH | SETTLED # NEW — V1 operates at PRE_AUTH

  device_id: string
  ip_address: string
  geo: { lat: decimal, lon: decimal, country: string }

  channel: WEB | MOBILE                          # narrowed — POS/ATM not relevant to CNP
  merchant_category: string
  card_present: boolean                          # false for V1 scenario
}
```

`payment_rail` is deliberately an enum with one value populated for V1 (`CARD_CNP`) rather than a free-text field — this is what makes "add UPI/bank-transfer later" a credible, low-friction extension instead of a rewrite: new rail, new enum value, new rail-specific evidence tools, same pipeline.

---

## 4. `get_merchant_risk()` — redefined

**Old shape (V1.0 — a label, not evidence):**
```text
Output { category, risk_band, prior_flags[], metadata }
```

**New shape (v1.1 — genuinely investigable):**
```text
get_merchant_risk {
  Input {
    merchant_id: string
    customer_id: string
  }

  Output {
    category: string
    onboarding_date: date
    chargeback_rate: decimal

    recent_fraud_report_count: number          # e.g. 3
    fraud_report_trend: RISING | STABLE | FALLING

    customer_prior_transactions_with_merchant: number   # 0 = never transacted before

    risk_band: LOW | MEDIUM | HIGH
  }
}
```

This is the direct answer to your manager's second question: **yes, Sentinel investigates merchant fraud/chargeback history as evidence**, and it's now a defined, retrievable, weighable fact — not an assumed label. `fraud_report_trend` in particular is what gives the Evidence Agent and Reasoning something genuinely ambiguous to reason over (3 reports could be noise or signal), which is exactly the kind of judgment call an LLM synthesis step is good for and a static rule isn't.

---

## 5. The V1 Demo Scenario — fully specified

| Dimension | Value |
|---|---|
| Payment rail | Card-not-present |
| Direction | Outgoing |
| Lifecycle stage | Pre-authorization (Sentinel can still hold this transaction) |
| Customer | Existing, 18-month tenure, established baseline |
| Account | Single account, linked accounts exist in fixture but unflagged at start |
| Card | Customer's primary card, `card_present = false` |
| Merchant | New-to-customer electronics e-commerce merchant, 3 fraud reports in the last 30 days, **rising** trend |
| Device | New, first seen 40 minutes before transaction |
| IP/location | Unusual vs. customer's established pattern (not impossible-travel) |
| Detected anomaly tags | `NEW_DEVICE`, `UNUSUAL_LOCATION`, `MERCHANT_RISK` |

**Seeded fixture twist (unchanged branching hook):** `get_device_history(device_id)` reveals this device was also seen on a different account 2 hours earlier. The agent must — on its own, not by pre-mapped rule — decide this is worth following and call `get_linked_entities`, which was not in the original `NEW_DEVICE` minimum-evidence floor. This is still your core agentic proof, unchanged from V1.0.

**What's new:** the merchant thread now runs in parallel. `get_merchant_risk` returns a rising fraud-report trend, which the minimum-evidence floor for `MERCHANT_RISK` already required — but now that data is genuinely worth reasoning over instead of being a flat label. This gives Reasoning and the Decision Robustness Scorer **two independently material signals** (device-linkage and merchant-risk-trend) instead of one, which makes a ROBUST classification meaningfully earned rather than automatic, and makes a FRAGILE classification (if you seed a variant with only one signal present) a real contrast to show live.

---

## 6. Policy — semantics clarified, rules unchanged

Because `authorization_stage = PRE_AUTH` is now explicit, the outcomes mean something concrete:

- **`AUTO_RESOLVE`** → release the authorization to proceed normally.
- **`ESCALATE`** → **hold the authorization** pending analyst review — the transaction does not settle until a human acts. This is meaningfully different from escalating a settled transaction (which could only flag it after the fact), and it's the reason pre-authorization was chosen as the lifecycle stage.

Rule set is unchanged from V1.0:

```text
IF evidence.completeness = PARTIAL                          → ESCALATE
IF reasoning.status = FAILED                                 → ESCALATE
IF risk_score >= HIGH AND value >= HIGH_VALUE
   AND evidence.completeness = COMPLETE                       → ESCALATE
IF risk_score >= MEDIUM AND findings.risk_assessment = HIGH
   AND evidence.completeness = COMPLETE                       → ESCALATE
IF risk_score <= LOW AND evidence.completeness = COMPLETE
   AND no hard-risk-tag AND findings.risk_assessment != HIGH  → AUTO_RESOLVE
OTHERWISE                                                     → ESCALATE
```

Still only `AUTO_RESOLVE | ESCALATE`. `BLOCK_HOLD` remains human-only, executed by the analyst on an already-escalated (held) case.

---

## 7. Minimum-Evidence Floor — unchanged, now grounded in real fields

| Anomaly tag | Required tool(s) |
|---|---|
| `NEW_DEVICE` | `get_device_history` |
| `UNUSUAL_LOCATION` | `get_ip_geovelocity` |
| `MERCHANT_RISK` | `get_merchant_risk` (now returning the expanded shape in §4) |
| `UNUSUAL_AMOUNT` | `get_behavioral_baseline` |
| `LINKED_ENTITY_ANOMALY` | `get_linked_entities` |

No change to the floor mechanism itself — only the content behind `get_merchant_risk` changed.

---

## 8. Everything else — confirmed unchanged from V1.0

- Single Cloud Run service, in-process modules, synchronous pipeline.
- Firestore only; no Pub/Sub, BigQuery, Vector Search/RAG in V1.
- Evidence Agent: Gemini Flash, bounded loop, max 6 calls, read-only tools.
- Reasoning: Gemini Pro, structured `CaseFindings`, citation validation.
- Decision Robustness Scorer: unchanged mechanism, now scoring two genuinely independent evidence threads (device-linkage, merchant-risk-trend) instead of one.
- Analyst UI: queue + case view, `CLEAR | BLOCK_HOLD | ESCALATE_SENIOR`.
- Build order (Weeks 1–5 from the original plan) is unchanged — Week 1's fixture-data work now includes seeding the merchant fraud-report history alongside the device/account fixtures already planned.

---

## 9. Path to additional rails (V2+, not now)

Because `payment_rail` is an enum and the evidence tools are already modular, adding a second rail later (e.g. outgoing bank transfer) means: add `BANK_TRANSFER` to the enum, add rail-specific evidence tools (e.g. `get_beneficiary_history` instead of `get_merchant_risk`), and let Policy rules branch on `payment_rail` where needed. The core pipeline — Detection → Evidence Agent → Reasoning → Robustness Scorer → Policy — does not change shape to support this. This is the credible expansion path your manager will want to hear about, without building any of it now.
