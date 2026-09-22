# Sentinel --- Project Overview

## 1. What is Sentinel?

**Sentinel is an AI-assisted fraud investigation and case-intelligence
system for financial transactions.**

It is designed to address a common gap in fraud operations:

> A fraud detection system can identify a suspicious transaction, but an
> investigator still needs to understand **why it is suspicious, what
> evidence supports or contradicts the signal, whether related activity
> exists, and what should happen next**.

Sentinel focuses on that investigation layer.

Instead of stopping at a risk score or anomaly flag, Sentinel:

``` text
Detect
  ↓
Investigate
  ↓
Gather evidence
  ↓
Explain
  ↓
Stress-test the conclusion
  ↓
Route safely
  ↓
Human decision when required
```

------------------------------------------------------------------------

# 2. Problem Statement

Financial institutions process a very large number of transactions.
Fraud detection systems can identify transactions that look unusual or
risky, but an alert by itself does not explain the complete situation.

When an alert is generated, an investigator may need to examine multiple
sources such as:

-   device history
-   customer behavior
-   IP and location information
-   linked accounts or entities
-   merchant history
-   supporting compliance information
-   previous transaction context

This creates an investigation gap between:

> **"Something looks suspicious."**

and

> **"We have enough evidence to understand this case and decide what
> should happen."**

The investigation process can therefore involve multiple evidence
lookups, interpretation of conflicting signals, manual review, and
documentation of the final decision.

Sentinel is designed to reduce that investigation gap.

------------------------------------------------------------------------

# 3. The Core Question Sentinel Answers

Sentinel is not primarily asking:

> **"Is this transaction fraud?"**

Instead, it asks:

> **"Why does this transaction require attention, what evidence supports
> or contradicts the concern, how robust is the conclusion, and what
> should happen next?"**

That distinction defines the product.

------------------------------------------------------------------------

# 4. Purpose of the Project

The purpose of Sentinel is to demonstrate an **evidence-driven AI
investigation workflow** for suspicious financial transactions.

The project combines:

-   measurable transaction detection
-   deterministic anomaly identification
-   bounded agentic investigation
-   grounded AI reasoning
-   evidence provenance
-   decision robustness analysis
-   deterministic policy routing
-   human analyst review
-   auditable case history

The project is intentionally designed so that AI adds value to the
investigation without receiving unrestricted financial authority.

The central principle is:

> **AI investigates and reasons. Deterministic policy controls automated
> disposition. Humans retain authority over sensitive actions.**

------------------------------------------------------------------------

# 5. Why Are We Building This?

A fraud score by itself is often insufficient for an investigator.

Consider a transaction that receives an elevated risk signal.

The useful questions are:

-   Is the device new?
-   Has that device appeared on another account?
-   Is the location unusual for this customer?
-   Is the transaction amount unusual?
-   Has the customer used this merchant before?
-   Is there relevant merchant history?
-   Are there related entities?
-   Is there evidence that contradicts the initial suspicion?
-   Does the conclusion depend on one piece of evidence?

A traditional alert can leave the investigator to perform these checks
manually.

Sentinel demonstrates a different workflow:

``` text
Transaction
    ↓
Risk + anomaly signals
    ↓
Relevant evidence automatically gathered
    ↓
AI investigates the evidence
    ↓
Grounded explanation
    ↓
Counterfactual robustness check
    ↓
Deterministic routing
    ↓
Human action when required
```

The goal is not simply to add AI.

The goal is to use AI where investigation requires contextual reasoning
while keeping sensitive decisions controlled.

------------------------------------------------------------------------

# 6. Who Is Sentinel For?

The primary user is a **fraud analyst / financial investigator**.

The analyst needs to:

-   understand why a case was flagged
-   inspect the underlying evidence
-   see supporting and counter evidence
-   understand evidence gaps
-   assess how robust the conclusion is
-   make a human decision
-   escalate a case when necessary
-   retain an auditable record of the investigation

A senior analyst handles cases escalated for additional human review.

The public investigation console provides a simplified entry point for
demonstrating the investigation capability without exposing protected
analyst case information.

------------------------------------------------------------------------

# 7. What Makes Sentinel Different?

Sentinel combines several stages into one investigation workflow.

## 7.1 Detection

A measurable detection layer produces:

-   risk score
-   risk band
-   anomaly tags
-   detection reasons

Detection is a signal, not the final decision.

------------------------------------------------------------------------

## 7.2 Agentic Investigation

The Evidence Agent can dynamically choose read-only evidence tools.

For example:

``` text
NEW_DEVICE
    ↓
get_device_history()
    ↓
Device history reveals another account
    ↓
Agent recognizes a relevant relationship
    ↓
get_linked_entities()
```

The second investigation step is selected because of evidence discovered
during the first step.

This makes the investigation genuinely adaptive rather than a fixed
sequence of API calls.

------------------------------------------------------------------------

## 7.3 Grounded Reasoning

Gemini receives structured evidence and produces findings containing:

-   supporting factors
-   counter-factors
-   evidence gaps
-   evidence citations
-   risk assessment
-   advisory recommendation

The system validates that citations refer to actual evidence.

The AI does not get to invent evidence or silently treat unsupported
claims as facts.

------------------------------------------------------------------------

## 7.4 Decision Robustness

Sentinel asks another important question:

> **"Would the conclusion still hold if an important piece of evidence
> were removed?"**

For a live counterfactual, Sentinel can remove an evidence fact and run
the reasoning process again.

The result can show:

-   `ROBUST`
-   `FRAGILE`

This gives an investigator information about the dependence of the
conclusion on individual evidence.

------------------------------------------------------------------------

## 7.5 Safe Decision Routing

The final automated routing is deterministic.

The AI cannot directly:

-   block a transaction
-   hold a transaction
-   clear a transaction
-   move money
-   approve or decline a financial transaction

Human analysts retain authority over sensitive actions.

------------------------------------------------------------------------

# 8. Current Product Scope

The current implementation focuses on:

**Outgoing card-not-present e-commerce authorization transactions.**

Current transaction characteristics include:

-   `payment_rail=CARD_CNP`
-   `direction=OUTGOING`
-   pre-authorization processing
-   web/mobile channels
-   card not present

The investigation context includes:

-   customer
-   account
-   card/payment instrument
-   merchant
-   device
-   IP/location
-   linked entities
-   supporting KYC context

The scope is intentionally narrow so that the investigation workflow can
be implemented, tested and demonstrated end to end.

------------------------------------------------------------------------

# 9. What Happens to a Transaction?

A simplified Sentinel investigation looks like this:

### Step 1 --- Transaction enters Sentinel

The transaction contains the information required for investigation.

### Step 2 --- Detection evaluates it

The detector produces a measurable risk score and deterministic anomaly
signals.

### Step 3 --- Investigation begins when required

The Evidence Agent gathers the evidence required for the detected
signals.

### Step 4 --- Agent branches when evidence reveals something new

The agent can select another relevant evidence source based on what it
discovers.

### Step 5 --- Gemini reasons over the evidence

The reasoning component produces a structured, grounded investigation
result.

### Step 6 --- Robustness is assessed

Sentinel evaluates whether the conclusion depends strongly on individual
evidence.

### Step 7 --- Deterministic policy routes the case

The current routing model distinguishes clean transactions from cases
requiring human attention.

A genuinely clean LOW-risk transaction with no anomaly can be
automatically resolved.

An anomalous transaction is routed to human review, including LOW-risk
anomalies.

Elevated-risk transactions are also handled through the review path
rather than being silently treated as clean.

### Step 8 --- Analyst acts when required

The analyst can:

-   `CLEAR`
-   `BLOCK_HOLD`
-   `ESCALATE_SENIOR`

A senior analyst can make the appropriate final human decision for an
escalated case.

------------------------------------------------------------------------

# 10. Risk, Anomaly and Decision Are Different

One of the most important concepts in Sentinel is that these are not the
same thing.

### Risk

How risky the transaction appears according to the detection model.

``` text
LOW
MEDIUM
HIGH
```

### Anomaly

What unusual signal was detected.

Examples:

``` text
NEW_DEVICE
UNUSUAL_LOCATION
UNUSUAL_AMOUNT
MERCHANT_RISK
LINKED_ENTITY_ANOMALY
KYC_ANOMALY
```

### Disposition

What the deterministic policy does with the investigation.

``` text
AUTO_RESOLVE
ESCALATE
```

### Human decision

What the analyst ultimately does.

``` text
CLEAR
BLOCK_HOLD
ESCALATE_SENIOR
```

Therefore:

> **LOW does not mean clean.**

> **HIGH does not mean fraud is confirmed.**

> **HUMAN_REVIEW does not mean the system failed.**

> **An anomaly can require human review even when the risk band is
> LOW.**

------------------------------------------------------------------------

# 11. The Safety Model

The project deliberately separates intelligence from authority.

``` text
Probabilistic AI
      |
      | investigates and reasons
      v
Evidence + Findings
      |
      v
Deterministic Policy
      |
      | routes automated outcome
      v
Human Analyst
      |
      | sensitive action
      v
Final Human Decision
```

This separation is important in a financial setting.

AI can help an investigator understand a case without becoming the
unrestricted authority over a customer's money.

------------------------------------------------------------------------

# 12. Why Use an Agent?

Sentinel does not add agents simply to increase the number of AI
components.

The Evidence Agent exists because evidence collection can be
conditional.

A fixed workflow might do:

``` text
Always call A
Always call B
Always call C
Always call D
```

An investigation agent can instead do:

``` text
Start with the known anomaly
        ↓
Retrieve relevant evidence
        ↓
Observe what was discovered
        ↓
Decide whether another evidence source is relevant
        ↓
Continue or stop
```

The agent is bounded by explicit tools, limits and timeouts.

It cannot leave the approved investigation boundary.

------------------------------------------------------------------------

# 13. Why Use Deterministic Policy?

A language model is useful for interpreting evidence, but financial
disposition should be predictable and auditable.

The deterministic policy layer therefore owns automated routing.

This provides:

-   repeatable behavior
-   explicit rules
-   versioned decisions
-   easier testing
-   easier auditing
-   a clear safety boundary

The policy does not need to "think."

Its job is to apply known rules consistently.

------------------------------------------------------------------------

# 14. Why Add Robustness Testing?

An explanation alone does not tell an investigator how dependent the
conclusion is on a particular fact.

Suppose an investigation says:

``` text
HIGH confidence because:
- new device
- unusual location
- linked account
```

Sentinel can ask:

> What happens if the linked-account evidence is removed?

If the conclusion changes, the investigator learns that the case was
highly dependent on that evidence.

If the conclusion remains supported, the investigation is more robust to
that individual evidence removal.

This is why robustness is part of the product rather than just a model
metric.

------------------------------------------------------------------------

# 15. What Sentinel Is Not

Sentinel is not:

-   a replacement for a bank's payment-processing system
-   a claim of access to real bank transaction infrastructure
-   a real external merchant-fraud intelligence service
-   a real bank KYC integration in the prototype
-   an autonomous financial decision maker
-   a chatbot presented as a fraud investigator
-   a collection of unrelated AI agents

The prototype uses synthetic/internal supporting data where real
institutional integrations are not available.

The architecture demonstrates where production integrations can later be
connected.

------------------------------------------------------------------------

# 16. Current Data Boundary

The prototype uses synthetic transaction and supporting evidence data.

This allows the project to demonstrate:

-   repeatable scenarios
-   controlled investigation paths
-   agent branching
-   grounded evidence
-   robustness testing
-   deterministic routing
-   analyst decisions

It also prevents the project from claiming access to private banking
systems or external fraud databases that are not actually connected.

------------------------------------------------------------------------

# 17. Expected Value

The intended value of Sentinel is to reduce the gap between:

``` text
Fraud alert
```

and

``` text
Evidence-backed investigation
```

The system brings relevant evidence into one investigation workflow and
structures the information an analyst needs to make a decision.

The prototype should therefore be evaluated on capabilities such as:

-   detection quality
-   evidence completeness
-   agent branching reliability
-   reasoning validity
-   citation validity
-   robustness behavior
-   routing correctness
-   end-to-end reliability
-   analyst workflow usability

Claims should be supported by measured evaluation results rather than
assumed performance.

------------------------------------------------------------------------

# 18. V1 → V2 Product Direction

The current product is deliberately narrow.

Once the investigation workflow is proven, the same product direction
can expand.

### Additional payment rails

Extend beyond card-not-present transactions to other supported financial
rails.

### More evidence

Connect governed production sources for:

-   KYC
-   merchant intelligence
-   device intelligence
-   network intelligence
-   transaction history

### Cross-case intelligence

Move from investigating one case at a time toward identifying
coordinated activity across accounts, devices and transactions.

### Precedent retrieval

Use prior cases as relevant investigation context when measurable value
is demonstrated.

### Higher-scale processing

Introduce event-driven infrastructure and independently scalable
services when transaction volume requires them.

### Analytics

Add historical investigation analytics and operational reporting.

### Production governance

Introduce stronger enterprise identity, access control, monitoring,
deployment and governance capabilities.

The product direction remains:

``` text
More evidence
     ↓
Better investigation
     ↓
Better explanation
     ↓
Better robustness
     ↓
Safer decisions
```

The safety boundary does not need to weaken as the system becomes more
capable.

------------------------------------------------------------------------

# 19. The One-Line Explanation

If someone asks:

> **"What is Sentinel?"**

Answer:

> **Sentinel is an AI-assisted fraud investigation system that goes
> beyond a fraud score by dynamically gathering relevant evidence,
> producing grounded explanations, testing the robustness of the
> investigation, and safely routing the case to automatic resolution or
> human review.**

------------------------------------------------------------------------

# 20. Short Problem → Solution Explanation

### Problem

Fraud detection can tell investigators that a transaction looks
suspicious, but investigators still need to gather and interpret
evidence before deciding what to do.

### Solution

Sentinel turns that alert into an evidence-driven investigation by
dynamically gathering relevant context, using AI to reason over grounded
evidence, testing whether the conclusion is robust, and routing the case
through deterministic policy and human review.

### Core differentiator

> **Sentinel does not stop at "this looks risky." It investigates why,
> shows the evidence, tests how dependent the conclusion is on that
> evidence, and keeps sensitive decisions under deterministic and human
> control.**
