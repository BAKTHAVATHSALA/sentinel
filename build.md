We have completed and verified:

- Frozen Sentinel contracts: commit 3019eba
- Synthetic Transaction Generator: commit 2e06a42
- 134/134 tests passing
- compileall clean
- main pushed
- working tree clean

NOW IMPLEMENT ONLY THE NEXT CHECKPOINT:

# CHECKPOINT: Detection Model + Deterministic Anomaly Tagging

Reference:
- Sentinel_V1_Build_Architecture_v1.1.md
- Sentinel_Technical_Design_Contracts_v1.1_FINAL_FROZEN-1.md
- build.md
- rules.md
- existing shared/contracts/*
- existing shared/generator/*

Do NOT implement:
- Evidence Agent
- Gemini reasoning
- robustness
- policy
- Firestore
- Pub/Sub
- BigQuery
- analyst UI
- deployment

This checkpoint is ONLY detection and deterministic anomaly tagging.

## 1. Detection architecture

Create a clean detection module, preferably:

shared/detection/

Separate:

A. model-based risk scoring
B. deterministic anomaly tagging

The detection layer must consume the existing V1 Transaction and generated historical/profile data.

It must produce the existing DetectionOutput contract.

Do NOT modify the frozen DetectionOutput contract unless an actual test/compile failure proves it is necessary.

## 2. DetectionOutput

Use the existing contract exactly.

The output must include the appropriate:
- risk score
- risk band
- anomaly tags
- model metadata/version as defined by the existing contract

Do not invent a second competing detection output model.

## 3. Risk scoring

Implement a deterministic, reproducible V1 detection model suitable for synthetic data.

A simple explainable ML approach is acceptable, such as an sklearn model, provided it is actually trained/fitted and used for prediction.

Do NOT use Gemini for detection.

Do NOT call an external fraud API.

Do NOT claim production-grade fraud accuracy.

The goal is a working prototype demonstrating:
transaction → detection score + signals.

Ensure:
- deterministic random state
- reproducible training/prediction
- clear model version
- no data leakage from future transaction information
- model can be trained from synthetic historical data

Use a clean training/prediction API.

## 4. Deterministic anomaly tagging

Implement deterministic rules for the 8 V1 anomaly tags:

1. NEW_DEVICE
2. UNUSUAL_LOCATION
3. UNUSUAL_AMOUNT
4. UNUSUAL_TIME
5. IMPOSSIBLE_TRAVEL
6. MERCHANT_RISK
7. LINKED_ENTITY_ANOMALY
8. KYC_ANOMALY

These rules must be explainable and deterministic.

Use the generated synthetic profiles/scenarios as the source of the underlying signals.

Do NOT simply copy a scenario name into the output.

The tag must be derived from actual transaction/history/profile data.

## 5. Important tag semantics

Implement clear, documented rules.

Examples:

NEW_DEVICE:
- transaction device is not established in the customer's historical device set.

UNUSUAL_LOCATION:
- transaction location materially differs from the customer's established location baseline.

UNUSUAL_AMOUNT:
- transaction amount is materially outside the customer's historical spending distribution.

UNUSUAL_TIME:
- transaction timestamp is outside the customer's established normal transaction-time window.

IMPOSSIBLE_TRAVEL:
- recent transactions for the same customer/device imply physically impossible travel velocity.

MERCHANT_RISK:
- merchant profile has the seeded merchant-risk indicators required by V1.

LINKED_ENTITY_ANOMALY:
- transaction/customer/account/device relationship is linked to another suspicious entity in the synthetic evidence/profile data.

KYC_ANOMALY:
- synthetic customer KYC status is anomalous.

The exact thresholds should be explicit constants/configuration, not magic numbers buried in functions.

## 6. No false coupling to future agents

Detection must NOT:
- call Evidence Agent tools
- call Gemini
- call policy
- determine AUTO_RESOLVE
- determine ESCALATE
- determine BLOCK_HOLD
- make a final fraud verdict

Detection only returns signals and risk assessment.

## 7. Demo scenario requirements

The existing flagship:

seeded_demo_case()

must produce detection output containing the intended signals:

- NEW_DEVICE
- UNUSUAL_LOCATION
- MERCHANT_RISK

Verify these are generated from the actual seeded data.

Also verify each of the other 7 scenarios independently produces its intended anomaly tag.

Do not weaken the rules merely to make tests pass.

## 8. Tests

Create:

tests/detection/

Test at minimum:

1. DetectionOutput validates.
2. Same input produces same detection output.
3. Different meaningful inputs can change the risk score.
4. Risk score remains within the contract's expected range.
5. Risk band is deterministic.
6. NEW_DEVICE is detected from actual device history.
7. UNUSUAL_LOCATION is detected from actual location baseline.
8. UNUSUAL_AMOUNT is detected from actual spending baseline.
9. UNUSUAL_TIME is detected from actual historical time behavior.
10. IMPOSSIBLE_TRAVEL is detected from actual recent transaction locations/timestamps.
11. MERCHANT_RISK is detected from actual merchant-risk data.
12. LINKED_ENTITY_ANOMALY is detected from actual entity relationships.
13. KYC_ANOMALY is detected from actual KYC data.
14. Flagship demo produces exactly the intended primary anomaly signals:
    NEW_DEVICE + UNUSUAL_LOCATION + MERCHANT_RISK
    and does not accidentally require the Evidence Agent.
15. Detection does not produce policy outcomes.
16. No Gemini/network calls are made by detection tests.
17. Existing 134 tests continue passing.

## 9. Testing quality

Do not create fake tests that merely inspect constants.

Tests should construct or use real generated data and exercise the actual detection logic.

Test negative/baseline cases where appropriate so the rules are shown to distinguish normal behavior from seeded anomalies.

## 10. Verification

Run:

pytest tests -v

Then:

python -m compileall shared tests

Then perform a real smoke test:

- generate normal transaction/history
- run detection
- generate flagship demo
- run detection
- print DetectionOutput
- confirm intended tags and risk result

Inspect:

git status
git diff --stat
git diff

Do not modify unrelated files.

## 11. Git

After all verification succeeds:

Stage ONLY detection implementation/tests and any directly necessary documentation changes.

Do not stage:
- .env
- credentials
- .venv
- caches
- IDE files
- generated datasets
- unrelated modifications

Commit exactly:

feat: add fraud detection and anomaly tagging

Push:

git push origin main

Then verify:

git status
git log -2 --oneline

Do not amend previous commits.
Do not force push.

## FINAL REPORT

Return:

A. Files created/modified
B. Detection model approach
C. Deterministic anomaly-tag rules
D. Flagship scenario detection result
E. All 8 scenario results
F. Test result
G. Compile result
H. Commit hash
I. Push result
J. Final git status
K. Any issues

Do not claim completion unless every verification step actually passed.