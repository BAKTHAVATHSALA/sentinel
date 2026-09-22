# Sentinel --- Architecture

## 1. Purpose

Sentinel is an AI-assisted fraud investigation and case-intelligence
system for card-not-present (CNP) outgoing e-commerce authorization
transactions.

The product is designed around a simple authority model:

> **AI investigates and reasons. Deterministic policy controls automated
> disposition. Humans retain authority over sensitive actions.**

The architecture deliberately keeps the first production-shaped
prototype small: one deployable Cloud Run service, in-process modules,
Firestore for live state and audit records, Gemini for
investigation/reasoning, and a React analyst experience.

The system is designed so that the same core investigation pipeline can
evolve to higher scale, additional payment rails, richer evidence
sources, and stronger operational infrastructure without changing the
core safety boundary.

------------------------------------------------------------------------

## 2. Product Boundary

### Current transaction scope

V1 handles:

-   outgoing transactions
-   card-not-present e-commerce activity
-   pre-authorization stage
-   `payment_rail=CARD_CNP`
-   `direction=OUTGOING`
-   `card_present=false`
-   `channel=WEB|MOBILE`

### Current entities

-   Customer
-   Account
-   Card / payment instrument
-   Merchant
-   Device
-   IP / location
-   Linked entities
-   Supporting KYC status

### Outside the current transaction scope

-   UPI
-   IMPS / NEFT / RTGS
-   ATM
-   incoming / receiving-side fraud
-   other payment rails

These are extension paths rather than requirements for the current
product.

------------------------------------------------------------------------

## 3. End-to-End Architecture

``` text
Transaction
    |
    v
Detection
(ML risk + deterministic anomaly tags)
    |
    v
Evidence Agent
(Gemini Flash)
    |
    +----> Device history
    +----> IP / geovelocity
    +----> Behavioral baseline
    +----> Linked entities
    +----> Merchant risk
    +----> Mock KYC
    |
    v
Gemini Reasoning
(Grounded structured findings)
    |
    v
Decision Robustness
(Fast path + live counterfactual)
    |
    v
Deterministic Policy
    |
    +----> AUTO_RESOLVED
    |
    +----> HUMAN_REVIEW
              |
              v
        Analyst Decision
          |      |      |
        CLEAR  BLOCK   ESCALATE
               & HOLD    SENIOR
    |
    v
Firestore
(case state, evidence, findings, decisions, audit events)
```

The deployed application runs backend modules and the compiled React UI
in the same Cloud Run service.

------------------------------------------------------------------------

## 4. Google Cloud Architecture

### Cloud Run

Hosts:

-   FastAPI backend
-   compiled React application
-   protected analyst experience
-   public investigation console

The application is deployed as one service to keep the prototype
operationally simple and reliable.

### Vertex AI / Gemini

Gemini is used in two distinct roles:

**Evidence Agent --- Gemini Flash**

-   selects read-only evidence tools
-   observes tool results
-   can branch to additional evidence based on discovered facts
-   operates inside a bounded loop
-   cannot perform financial actions

**Reasoning --- Gemini Pro**

-   receives structured transaction, detection, and evidence context
-   produces grounded structured findings
-   identifies supporting factors, counter-factors and evidence gaps
-   cites actual evidence facts
-   provides an advisory assessment

Neither role has authority to clear, block, hold, release, or move
money.

### Firestore

Firestore stores the live case model and audit events.

The case contains the material investigation state required by the
analyst workflow, including:

-   transaction
-   detection output
-   evidence bundle
-   reasoning findings
-   robustness result
-   policy result
-   case state
-   assignment
-   human decisions
-   audit history

### Firebase Authentication

Firebase Authentication provides analyst identity.

The Firebase UID is the canonical analyst/actor identity used by the
backend.

Roles:

-   `ANALYST`
-   `SENIOR_ANALYST`

The backend verifies the Firebase ID token on protected case operations.

------------------------------------------------------------------------

## 5. Detection

Detection is the first-pass risk signal.

It combines:

1.  a measurable ML detector
2.  deterministic anomaly tagging

The detector produces:

-   `risk_score`
-   `risk_band`
-   `anomaly_tags[]`
-   detection reasons
-   model/version metadata

Risk bands:

-   **LOW:** `< 0.40`
-   **MEDIUM:** `0.40 <= score < 0.75`
-   **HIGH:** `>= 0.75`

Risk and anomaly are separate concepts:

-   **Risk** describes how risky the transaction appears.
-   **Anomaly** describes what unusual signal was detected.
-   **Clean** means no anomaly tags.
-   **Disposition** is the deterministic routing decision.

A LOW-risk transaction can still contain an anomaly.

A HIGH-risk transaction is not itself proof of fraud.

------------------------------------------------------------------------

## 6. Anomaly Signals

Current anomaly signals include:

### Statistical / behavioral signals

-   `NEW_DEVICE`
-   `UNUSUAL_LOCATION`
-   `UNUSUAL_AMOUNT`

### Structural / higher-risk signals

-   `MERCHANT_RISK`
-   `LINKED_ENTITY_ANOMALY`
-   `KYC_ANOMALY` where exercised by the supporting context

The Evidence Agent does not blindly call every tool. The system enforces
a minimum evidence floor for relevant anomaly signals while allowing the
agent to branch when new evidence reveals another investigation path.

------------------------------------------------------------------------

## 7. Evidence Agent

The Evidence Agent is the genuinely agentic component.

Available read-only tools:

1.  `get_device_history`
2.  `get_ip_geovelocity`
3.  `get_behavioral_baseline`
4.  `get_linked_entities`
5.  `get_merchant_risk`
6.  `get_mock_kyc_status`

The agent is bounded by:

-   explicit tool allow-list
-   maximum six tool calls
-   per-tool timeout
-   overall investigation deadline
-   structured tool errors
-   minimum-evidence requirements

### Why it is genuinely agentic

The agent is not simply given a fixed list of tools to execute.

Example:

``` text
Detection
NEW_DEVICE
    |
    v
Agent calls get_device_history
    |
    v
Device history reveals the device
was previously seen on another account
    |
    v
Agent decides that linked-account evidence
is relevant
    |
    v
Agent calls get_linked_entities
```

The second call is selected because of what the first call revealed.

That branching behavior is the important distinction between an evidence
agent and a scripted sequence.

------------------------------------------------------------------------

## 8. Gemini Reasoning

Reasoning receives:

-   transaction facts
-   detection output
-   collected evidence
-   evidence citations

It returns structured findings containing:

-   risk assessment
-   summary
-   supporting factors
-   counter-factors
-   evidence gaps
-   evidence citations
-   advisory disposition
-   model metadata

Every citation must point to an actual evidence fact.

Invalid structured output or invalid citations are not silently
accepted. The system can retry the constrained reasoning request and
safely route the case to human review if the required output cannot be
validated.

Gemini is advisory.

The deterministic policy layer remains the automated authority.

------------------------------------------------------------------------

## 9. Decision Robustness

Sentinel separately asks:

> **How dependent is this investigation on individual evidence?**

The robustness capability has two levels.

### Fast path

A deterministic materiality-based assessment identifies whether the
findings appear dependent on a single high-materiality factor.

### Live counterfactual

For an interactive case review, Sentinel can:

1.  remove a selected evidence fact
2.  rebuild the evidence bundle
3.  call reasoning again
4.  compare the resulting assessment
5.  show whether the conclusion changes

Possible result:

-   `ROBUST`
-   `FRAGILE`

The counterfactual result is advisory. It does not directly control
financial disposition.

------------------------------------------------------------------------

## 10. Deterministic Policy

Policy is the only automated disposition authority.

The policy can produce:

-   `AUTO_RESOLVE`
-   `ESCALATE`

It cannot produce an automated `BLOCK_HOLD`.

### Current routing semantics

**Clean + LOW + complete evidence + non-HIGH findings**

→ `AUTO_RESOLVE`

**Any anomaly**

→ `HUMAN_REVIEW`

This includes LOW-risk anomalies.

**MEDIUM or HIGH risk with no anomaly**

→ `HUMAN_REVIEW`

This prevents an elevated-risk transaction from being silently
auto-resolved merely because no anomaly tag was generated.

**Incomplete evidence or failed reasoning**

→ `HUMAN_REVIEW`

The policy is deterministic and versioned.

------------------------------------------------------------------------

## 11. Human Decision Model

Cases routed to human review are assigned to an active analyst.

### Analyst

Can:

-   `CLEAR`
-   `BLOCK_HOLD`
-   `ESCALATE_SENIOR`

### Senior analyst

Can:

-   `CLEAR`
-   `BLOCK_HOLD`

A senior analyst cannot escalate again.

### Escalation

When an analyst selects `ESCALATE_SENIOR`:

-   case state remains `HUMAN_REVIEW`
-   ownership moves to the selected senior analyst
-   the original analyst retains escalation history
-   the senior becomes responsible for the next human decision

Human decisions are persisted through a transactional path so that the
first valid decision wins in a race.

------------------------------------------------------------------------

## 12. Case Lifecycle

``` text
Transaction received
        |
        v
Detection
        |
        +---- clean + LOW
        |          |
        |          v
        |     AUTO_RESOLVED
        |
        +---- anomaly / elevated risk
                   |
                   v
             HUMAN_REVIEW
                   |
          +--------+---------+
          |        |         |
        CLEAR   BLOCK_HOLD  ESCALATE_SENIOR
          |        |         |
          v        v         v
      FINALIZED  FINALIZED  HUMAN_REVIEW
                              |
                              v
                       Senior analyst
```

The automated path never performs a human-only action.

------------------------------------------------------------------------

## 13. Auditability

Material case activity is traceable through:

-   case ID
-   transaction ID
-   evidence provenance
-   model metadata
-   prompt metadata where applicable
-   policy version
-   analyst identity
-   human decision
-   escalation history
-   timestamps

The goal is to make a case reconstructable rather than merely displaying
the final answer.

------------------------------------------------------------------------

## 14. Security Model

### Public surface

The public investigation console may submit transaction documents and
receive the safe investigation summary required for the user experience.

It does not expose protected analyst case details.

### Protected surface

Analyst case operations require Firebase authentication.

The backend derives identity from the verified token rather than
trusting a client-supplied analyst identity.

Firestore client-side direct access is not used for case mutation.
Protected operations go through the backend.

### Financial safety boundary

No probabilistic component can directly:

-   block
-   hold
-   clear
-   release
-   approve
-   decline
-   move money

Those actions remain under deterministic policy or human authority as
defined by the workflow.

------------------------------------------------------------------------

## 15. V1 Deployment Shape

The current deployment is intentionally simple:

``` text
Browser
   |
   v
Cloud Run
   |
   +-- React UI
   |
   +-- FastAPI
         |
         +-- Detection
         +-- Evidence Agent
         +-- Gemini Reasoning
         +-- Robustness
         +-- Policy
         +-- Case Store
         |
         +-- Vertex AI / Gemini
         +-- Firestore
         +-- Firebase Auth verification
```

This structure minimizes deployment and coordination overhead while
keeping the internal boundaries clear.

------------------------------------------------------------------------

# 16. Evolution from V1 to V2

V2 should scale the system around the same investigation and safety
model rather than replacing it.

## V2 Evolution 1 --- Event-driven processing

Move long-running and burst-sensitive work behind an event backbone such
as Pub/Sub.

Potential flow:

``` text
Transaction Source
      |
      v
Pub/Sub
      |
      +--> Detection
      |
      +--> Case / Investigation events
      |
      +--> Evidence processing
      |
      +--> Audit / analytics
```

Benefits:

-   burst absorption
-   asynchronous processing
-   retry handling
-   dead-letter paths
-   independent scaling
-   clearer service boundaries

The deterministic policy and human authority model remain unchanged.

------------------------------------------------------------------------

## V2 Evolution 2 --- Separate compute responsibilities

When scale justifies it, split the in-process modules into independently
deployable services.

Possible boundaries:

-   transaction intake
-   detection
-   investigation orchestration
-   evidence services
-   reasoning
-   policy
-   analyst API

The logical pipeline remains the same.

The split is an operational scaling decision, not a change to product
semantics.

------------------------------------------------------------------------

## V2 Evolution 3 --- Historical analytics

Introduce an analytical store such as BigQuery for:

-   historical transaction analysis
-   investigation metrics
-   model evaluation
-   policy performance
-   analyst outcome analysis
-   operational reporting

Firestore remains appropriate for live case state; analytical storage
serves long-term query and reporting workloads.

------------------------------------------------------------------------

## V2 Evolution 4 --- Richer evidence

Replace selected synthetic/mock evidence sources with governed
production integrations.

Examples:

-   real merchant-risk sources
-   real KYC/compliance systems
-   device intelligence
-   network intelligence
-   account relationship data
-   bank-internal transaction history

The Evidence Agent continues to access these through explicit read-only
tool contracts.

------------------------------------------------------------------------

## V2 Evolution 5 --- Additional payment rails

The transaction model already separates the payment rail from the
investigation pipeline.

Future rails can add:

-   rail-specific transaction fields
-   rail-specific evidence tools
-   rail-specific policy rules

Examples:

-   bank transfers
-   UPI
-   other institution-supported payment flows

The core sequence remains:

``` text
Detection
→ Evidence
→ Reasoning
→ Robustness
→ Policy
→ Human review
```

------------------------------------------------------------------------

## V2 Evolution 6 --- Precedent retrieval

If evaluation demonstrates measurable value, add a governed
precedent/retrieval layer.

The objective should not be:

> "Add RAG because the product uses AI."

The objective should be:

> "Use prior cases to provide relevant precedent and explain meaningful
> differences that affect investigation reasoning."

A retrieval system should be added only when it improves grounded
investigation quality enough to justify its operational complexity.

------------------------------------------------------------------------

## V2 Evolution 7 --- Stronger correlation and fraud-ring analysis

As transaction volume grows, introduce richer cross-case correlation.

Possible capabilities:

-   cross-account device relationships
-   merchant/customer relationship patterns
-   temporal correlation
-   coordinated activity detection
-   graph-based investigation

A graph store can become useful when relationship volume and query
patterns justify it.

------------------------------------------------------------------------

## V2 Evolution 8 --- Production observability

Expand operational visibility with:

-   distributed tracing
-   stage-level latency
-   tool failure rate
-   investigation latency
-   model latency and cost
-   escalation rate
-   auto-resolution rate
-   evidence completeness
-   reasoning validation rate
-   policy outcomes
-   analyst workload
-   model drift

Operational metrics should remain separate from decision authority.

------------------------------------------------------------------------

## V2 Evolution 9 --- Production security and governance

As the system moves beyond prototype use:

-   stronger service-to-service identity
-   least-privilege IAM
-   secret management
-   audit-grade access controls
-   data retention policies
-   encryption/key management where required
-   rate limiting
-   abuse protection
-   environment separation
-   deployment automation
-   controlled model/version rollout

------------------------------------------------------------------------

## 17. V2 Design Principle

The most important V2 rule is:

> **Scale the infrastructure without weakening the authority boundary.**

More models, more agents, more data and more services should never mean
that a probabilistic component gains direct authority over a sensitive
financial action.

The architectural center remains:

``` text
AI investigates
      ↓
Evidence is grounded
      ↓
Reasoning is explainable
      ↓
Robustness is tested
      ↓
Deterministic policy routes
      ↓
Humans retain sensitive-action authority
```

------------------------------------------------------------------------

## 18. Architecture Decision Summary

  ---------------------------------------------------------------------------
  Concern                 Current approach        Evolution path
  ----------------------- ----------------------- ---------------------------
  Compute                 One Cloud Run service   Independently scalable
                                                  services where justified

  Communication           In-process synchronous  Event-driven messaging
                          calls                   where needed

  Live state              Firestore               Firestore + analytical
                                                  store

  Analytics               Application/offline     BigQuery / managed
                          evaluation              analytics

  Evidence                Six read-only sources   Governed production
                                                  integrations

  AI investigation        Bounded Gemini Evidence More capable evidence
                          Agent                   orchestration

  Reasoning               Gemini structured       Model/version evolution
                          reasoning               with evaluation

  Robustness              Fast path + live        Broader
                          counterfactual          counterfactual/evaluation
                                                  framework

  Policy                  Deterministic rules     Versioned governed policy
                                                  service

  Payment scope           CARD_CNP outgoing       Additional rail-specific
                                                  pipelines

  Correlation             Seeded linked-entity    Cross-case/graph
                          evidence                correlation

  Retrieval               No precedent retrieval  Add retrieval when
                          in current scope        measurable value is
                                                  demonstrated

  Observability           Structured application  Distributed tracing +
                          telemetry               operational dashboards

  Auth                    Firebase Authentication Enterprise identity
                                                  integration if required

  UI                      React analyst console   Enterprise workflow
                                                  integrations
  ---------------------------------------------------------------------------

------------------------------------------------------------------------

## 19. Guiding Principle

Sentinel should grow from a small, understandable investigation product
into a production-scale investigation platform without losing the
property that makes the system trustworthy:

> **The AI can investigate deeply without being allowed to exercise
> unsafe financial authority.**
