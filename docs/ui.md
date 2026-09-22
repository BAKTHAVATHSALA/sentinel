# Sentinel --- UI Guidelines

## 1. Purpose

This document translates the Sentinel architecture and design system
into page-level UI behavior.

It defines what each screen should communicate, what information appears
first, what can be expanded, and which states must never be confused.

This document is a presentation and interaction guide. It does not
redefine backend contracts or decision logic.

------------------------------------------------------------------------

# 2. Product UX Model

The Sentinel experience should tell one continuous story:

``` text
User submits transaction
        ↓
Sentinel detects signals
        ↓
Sentinel investigates evidence
        ↓
Sentinel explains the evidence
        ↓
Sentinel tests robustness
        ↓
Deterministic policy routes the case
        ↓
Human acts when required
```

The interface should always make the current point in that story
obvious.

------------------------------------------------------------------------

# 3. Public Investigation Console

## Purpose

The public console is the entry point for transaction investigation.

Primary action:

> Upload a transaction record.

Supported input:

-   PDF
-   DOCX

The page should not expose internal analyst functionality.

## Layout

``` text
SENTINEL

Transaction Investigation Console

Upload transaction records and Sentinel will investigate them
with evidence-driven AI and deterministic policy controls.

[ Upload / Drop Zone ]
```

Keep the page focused.

Do not add:

-   demo scenario buttons
-   internal policy controls
-   raw Firestore data
-   analyst-only information
-   technical debugging panels

------------------------------------------------------------------------

# 4. Public Investigation Flow

Use this sequence:

``` text
Upload
  ↓
Extract
  ↓
Validate
  ↓
Preview
  ↓
Run Investigation
  ↓
Result
```

The UI may animate progression, but displayed status must reflect actual
application state.

Do not invent backend telemetry.

------------------------------------------------------------------------

# 5. Public Result --- AUTO-RESOLVED

When the actual backend result is automated resolution, the primary
message should be:

``` text
AUTO-RESOLVED

No anomalies found

No analyst action required
```

Do not make `LOW RISK` the dominant explanation.

The product reason is:

> the transaction met the clean automated-resolution conditions.

Do not expose protected policy identifiers or raw policy reasons.

------------------------------------------------------------------------

# 6. Public Result --- HUMAN REVIEW

When the actual backend routes to human review:

``` text
HUMAN REVIEW

Risk: LOW / MEDIUM / HIGH

Analyst investigation required

Signals:
[New device] [Unusual location] ...

Investigation status:
...
Assigned analyst:
...

[Open Case]
```

Use the actual backend risk and anomaly values.

Never infer a risk level from the anomaly names.

Never display AUTO-RESOLVED copy in this state.

------------------------------------------------------------------------

# 7. Analyst Navigation

Authenticated analyst pages should have a consistent header:

``` text
SENTINEL
My Cases

                         Display Name
                         Analyst / Senior Analyst
                         Logout
```

The header should be persistent across analyst workflow pages.

------------------------------------------------------------------------

# 8. Analyst Dashboard

The analyst dashboard is a work queue, not an analytics product.

## Metrics

Show exactly:

-   Total Cases
-   Open Cases
-   Closed Cases
-   Block & Hold
-   Escalated to Senior

No charts, percentages or fabricated trends are required.

### Definitions

**Total Cases**

Cases currently assigned to the analyst or represented in their
dashboard scope according to the backend dashboard query.

**Open Cases**

Cases in `HUMAN_REVIEW` in the analyst's dashboard scope.

**Closed Cases**

Cases in `FINALIZED` in the analyst's dashboard scope.

**Block & Hold**

Finalized cases whose final human disposition is `BLOCK_HOLD`.

**Escalated to Senior**

Cases that the current analyst personally escalated to a senior analyst.

This metric is based on persisted escalation attribution, not current
assignment.

------------------------------------------------------------------------

# 9. Senior Analyst Dashboard

Show:

-   Total Cases
-   Open Cases
-   Closed Cases
-   Block & Hold

Do not show `Escalated to Senior` to senior analysts.

Keep the same visual treatment as the analyst dashboard.

------------------------------------------------------------------------

# 10. Case Queue

The queue should optimize for fast scanning.

Recommended visible columns:

-   Risk
-   Robustness
-   Why flagged
-   Amount
-   Merchant
-   State
-   Age

Use badges for:

-   LOW
-   MEDIUM
-   HIGH
-   ROBUST
-   FRAGILE
-   HUMAN REVIEW
-   FINALIZED

The queue should not expose unnecessary raw technical data.

------------------------------------------------------------------------

# 11. Case Detail

The case detail page should answer five questions in order:

1.  What case is this?
2.  Where is it in the investigation?
3.  What did the investigation find?
4.  What evidence supports that conclusion?
5.  What action can the analyst take?

## Page order

``` text
Case Header
↓
Investigation Pipeline
↓
Investigation Summary
↓
Evidence
↓
Gemini Assessment
↓
Robustness
↓
Policy
↓
Human Decision
```

------------------------------------------------------------------------

# 12. Case Header

Show prominently:

-   case state
-   case ID
-   transaction amount
-   merchant
-   actual risk
-   anomaly signals
-   key transaction context

Example:

``` text
HUMAN REVIEW                         HIGH

$155.00   merch_batch_home_005

[New device] [Unusual location] [Linked entity]

Device ...
Location ...
Card ...
Channel ...
```

The header should be understandable without reading the rest of the
page.

------------------------------------------------------------------------

# 13. Investigation Pipeline

Show:

``` text
Detection
→ Evidence
→ Reasoning
→ Robustness
→ Policy
→ Human decision
```

Example:

``` text
Detection       Evidence       Reasoning
High risk      Complete       Success

Robustness     Policy         Human decision
Robust         Escalate       Awaiting
```

Interpretation:

-   completed automated stages → teal
-   policy escalation → amber
-   awaiting human action → amber
-   actual technical failure → red

The pipeline is not an error indicator.

------------------------------------------------------------------------

# 14. Investigation Summary

The summary should reduce cognitive load.

Recommended structure:

``` text
Investigation summary

AI assessment · Medium · Advisory

Supporting factors
• ...

Counter-evidence
• ...

Evidence gaps
• ...
```

Keep this concise.

Do not repeat the entire Gemini narrative here.

Do not generate new AI text in the frontend.

Use existing findings and evidence.

------------------------------------------------------------------------

# 15. Evidence

Evidence should be collapsed by default where practical.

Example:

``` text
Device history
New device confirmed                         View →

IP geovelocity
Location differs from baseline              View →

Linked entities
No supporting linked relationship found     View →
```

When expanded, show the complete evidence.

Technical details can include:

-   exact values
-   timestamps
-   source record IDs
-   evidence status
-   citations
-   derived/verified status

Never remove evidence merely to make the page shorter.

------------------------------------------------------------------------

# 16. Gemini Assessment

Label clearly:

> **Gemini's assessment · Advisory, not a decision**

Do not say:

> Gemini decided

or

> Gemini approved

or

> Gemini blocked

Gemini may provide an advisory recommendation.

The deterministic policy and human workflow determine action.

------------------------------------------------------------------------

# 17. Robustness

Default view:

``` text
ROBUST

Assessment remains supported when
individual evidence factors are removed.

[View / test counterfactual]
```

When a live counterfactual is run, show:

``` text
LIVE COUNTERFACTUAL

Removed:
Merchant history

Result:
ROBUST

Assessment remained unchanged.
```

Clearly distinguish live results from fast-path estimates.

------------------------------------------------------------------------

# 18. Policy

The policy panel should lead with the human-readable outcome:

``` text
POLICY

HUMAN REVIEW

Human investigation required.
```

Technical details may be expandable:

-   policy rule
-   rule version
-   policy reasons
-   relevant risk/anomaly conditions

Do not expose raw policy internals on the public console.

------------------------------------------------------------------------

# 19. Human Decision

This is the final authority section.

Show:

``` text
Human decision · Final authority

☐ I have reviewed the evidence above

[Clear]
[Block & Hold]
[Escalate to Senior]
```

Buttons must respect the user's role and case state.

Do not expose human decision controls to public users.

------------------------------------------------------------------------

# 20. Decision States

## CLEAR

After a successful clear:

``` text
Decision finalized

Final decision: Clear
Case ID: ...
Actor: ...
Timestamp: ...

[Back to My Cases]
[Logout]
```

Do not reload the case into a stale decision form.

## BLOCK & HOLD

Use the same finalized confirmation structure.

Make the action clearly distinguishable as a sensitive financial action.

## ESCALATE TO SENIOR

After escalation:

``` text
Case escalated

Assigned senior:
Name

Status:
Human review continues

Ownership has moved to the senior analyst.
```

Do not immediately reload the case as though the original analyst still
owns it.

Provide:

-   Back to My Cases
-   Logout

------------------------------------------------------------------------

# 21. Senior Analyst After Escalation

The senior analyst should receive the case in their normal queue.

They can:

-   Clear
-   Block & Hold

They cannot escalate again.

------------------------------------------------------------------------

# 22. Risk Semantics

Never combine risk, anomaly and disposition into one concept.

Use:

``` text
Risk
LOW / MEDIUM / HIGH

Anomalies
NEW_DEVICE
UNUSUAL_LOCATION
...

Disposition
AUTO-RESOLVED / HUMAN REVIEW

Human decision
CLEAR / BLOCK & HOLD / ESCALATE TO SENIOR
```

Important:

> LOW does not mean CLEAN.

> HIGH does not mean fraud is confirmed.

> HUMAN REVIEW does not mean the system failed.

> ESCALATE is a successful deterministic routing result.

------------------------------------------------------------------------

# 23. Clean Transaction UX

For a genuinely clean transaction:

``` text
AUTO-RESOLVED

No anomalies found

No analyst action required
```

Avoid presenting a large LOW-risk badge as the reason for resolution.

The user should understand that Sentinel found no anomaly requiring
investigation and the transaction satisfied the clean automated path.

------------------------------------------------------------------------

# 24. Anomalous Transaction UX

For any anomaly:

``` text
HUMAN REVIEW

Risk: LOW / MEDIUM / HIGH

Signals:
[New device]
[Unusual location]

Analyst investigation required
```

Even a LOW-risk anomaly requires human review according to the current
routing model.

------------------------------------------------------------------------

# 25. Error UX

Technical failure:

``` text
Investigation unavailable

Sentinel could not complete the required investigation.

Please retry.
```

Do not expose stack traces to normal users.

Do not call a technical failure:

-   fraud
-   high risk
-   human review

unless the actual backend state says so.

------------------------------------------------------------------------

# 26. Loading UX

Loading states should communicate the current legitimate application
stage.

Good:

``` text
Extracting transaction
Validating transaction
Running investigation
Preparing results
```

Avoid fake progress percentages.

Avoid claiming that a specific AI tool ran before the backend has
actually done so.

------------------------------------------------------------------------

# 27. Accessibility and Interaction

All important actions must work with:

-   mouse
-   keyboard
-   trackpad

Use visible focus states.

Do not rely only on color.

Maintain readable contrast.

The page can hide the physical scrollbar visually while retaining normal
scrolling.

------------------------------------------------------------------------

# 28. Final UX Story

The complete Sentinel experience should feel like one circle:

``` text
USER
  |
  | submits transaction
  v
SENTINEL DETECTS
  |
  | identifies unusual signals
  v
SENTINEL INVESTIGATES
  |
  | agent gathers relevant evidence
  v
SENTINEL EXPLAINS
  |
  | grounded findings + citations
  v
SENTINEL STRESS-TESTS
  |
  | robustness / counterfactual
  v
SENTINEL ROUTES
  |
  +---- clean + low + no anomaly
  |             |
  |             v
  |        AUTO-RESOLVED
  |
  +---- anomaly / elevated risk
                |
                v
           HUMAN REVIEW
                |
                v
          ANALYST DECISION
                |
                v
       CLEAR / BLOCK & HOLD /
       ESCALATE TO SENIOR
```

The UI should make that story visible without requiring the user to
understand the internal implementation.

------------------------------------------------------------------------

# 29. Final UI Principle

The product should never feel like:

> "Here are six AI outputs. Figure out what happened."

It should feel like:

> **"Here is the case, here is why it needs attention, here is the
> evidence, here is how the system tested its conclusion, and here is
> the action available to you."**
