# Sentinel V1 -- Evaluation Numbers

Build Checklist Phase 5.5. Every number below is read directly from a
committed JSON artifact produced by running the real Sentinel pipeline (real
detector model, real Gemini Flash/Pro, real Firestore) -- none of these
numbers are estimated or adjusted by hand. Each section names its source
artifact so the number can be traced back to how it was produced.

---

## Detection

Source: `eval/detection_baseline.json` (Phase 1), evaluated on the held-out
split (`data/processed/X_held_out.parquet` / `y_held_out.csv`, 56,962 rows,
98 fraud / 56,864 legitimate), no retraining or hyperparameter tuning
performed against it.

| Metric | Value |
|---|---|
| Precision | 0.0577 |
| Recall | 0.9184 |
| ROC-AUC | 0.9723 |
| PR-AUC | 0.7190 |
| False-negative rate | 0.0816 |

Confusion matrix: TP=90, FP=1469, TN=55,395, FN=8.

**Reading this honestly:** recall and ROC-AUC are strong -- the detector
catches 90/98 fraud cases (91.8%) and ranks fraud far above legitimate
traffic overall. Precision is intentionally low (0.058): this is a
detector tuned to *flag generously* and hand ambiguous cases to the
Evidence Agent / Reasoning / Policy pipeline, not to make a final call
itself -- exactly the point of that pipeline existing. A high-precision
detector alone would be a different (and, for this design, wrong) product.

## Evidence Agent

Source: `eval/evidence_agent_branching.json` (Phase 2.4), 10 independent
live runs of the branching-proof scenario against real Gemini Flash.

| Metric | Value |
|---|---|
| Branching success rate | 10/10 |
| `get_device_history` called first | 10/10 |
| Evidence floor satisfied | 10/10 |

All 10 runs genuinely discovered the cross-account device signal and chose
to call `get_linked_entities` on their own -- not a scripted follow-up
(see that file's `fixed_mapping_failure_pattern_note` for what a fake
version of this would look like instead).

## Reasoning

Source: `eval/reasoning_validity.json` (generated this session,
`scripts/evaluate_reasoning.py`). Real Gemini Pro reasoning calls against
the real, already-persisted evidence bundles for the 4 flagged Phase 1.4
scenarios (`branching_proof`, `merchant_risk_trend`, `partial_evidence`,
`signature_fraud` -- `clean_normal` never reaches Reasoning, since clean
transactions skip investigation entirely). Measured per attempt, since a
case can require a reprompt (Contracts S17).

| Metric | Value |
|---|---|
| Attempts measured | 4 |
| Schema-validity rate | 4/4 = 1.00 |
| Citation-validity rate | 4/4 = 1.00 |

**Known limitation:** every attempt in this run succeeded on the first
try, so this sample contains zero reprompt events -- it demonstrates that
real Gemini Pro output was valid, but it does not exercise the reprompt
path itself. The reprompt-then-`FAILED` fail-safe is separately proven with
a real, non-mocked run in `scripts/seed_ui_demo_cases.py` (a genuine
`reasoning.status = FAILED` case, `case_706c361f6116`, forced through the
same real bounded-retry logic with a scripted-invalid Gemini response, then
resolved via real Policy rule P-005) -- that is correctness evidence for
the fail-safe path, not a citation-validity-rate data point, and is kept
separate for that reason. Four attempts is also a small sample by
construction (Phase 1.4 built exactly 5 seed scenarios, 4 of them
flagged) -- this is the full real scenario set that exists, not a subset
chosen to look favorable.

## End-to-end

Source: `eval/pipeline_scenarios_proof.json` (Phase 4.3, re-run this
session against the corrected orchestrator), all 5 seeded Phase 1.4
scenarios -- the full set that exists (the checklist suggests ~10-20; only
5 were built in Phase 1.4, and fabricating additional scenarios to hit that
range was out of scope for this task). "Reasonable?" is this session's own
assessment against the real evidence each case actually produced, not a
number from any artifact.

| Scenario | Signal(s) | Policy outcome | Rule | Reasonable for a human analyst? |
|---|---|---|---|---|
| `clean_normal` | none | AUTO_RESOLVE | -- (Policy not invoked; investigation skipped) | Yes -- no anomaly signal, straight-through processing is correct. |
| `branching_proof` | NEW_DEVICE, device linked to a second account under KYC review 2h earlier | ESCALATE | P-002 | Yes -- a device shared with an account under active KYC review is a genuine cross-account red flag. |
| `merchant_risk_trend` | MERCHANT_RISK, rising fraud-report trend, customer's first transaction with this merchant | ESCALATE | P-002 | Yes -- a rising fraud trend at a brand-new merchant relationship is a textbook escalation case. |
| `partial_evidence` | NEW_DEVICE, but `get_device_history` deliberately times out | ESCALATE | P-001 | Yes -- evidence could not be completed; escalating rather than guessing is exactly the fail-safe behavior Contracts requires. |
| `signature_fraud` | NEW_DEVICE + UNUSUAL_LOCATION + MERCHANT_RISK, device linked to a compromised account, ~1758km location shift, HIGH-risk merchant | ESCALATE | P-002 | Yes -- multiple independent strong signals; this is the clearest possible escalation case. |

5/5 outcomes match both their expected label and a reasonable analyst's
judgment. **Known limitation:** because these 5 scenarios were built in
Phase 1.4 specifically to prove clean-cut behavior (an unambiguous clean
case and four unambiguous escalation cases), this table does not exercise
a genuinely borderline case where a reasonable analyst might disagree with
Policy -- none of the 5 seed scenarios are constructed to be ambiguous.
That is a real gap in what this evaluation set can show, not a claim that
Sentinel handles ambiguous cases correctly.

---

## Supplementary: Decision Robustness Scorer

Not one of the five required 5.5 categories, but directly relevant to the
same "does the automated output deserve trust" question and already real,
committed evidence: `eval/robustness_scorer_proof.json` (Phase 3) shows the
fast-path estimate and a real live-counterfactual re-call (a second, real
Gemini Pro call on a reduced evidence bundle) genuinely disagreeing on at
least one seeded variant -- not ROBUST everywhere, not FRAGILE everywhere.
