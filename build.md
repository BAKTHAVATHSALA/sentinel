We have completed and committed the Sentinel frozen contract layer.

Current verified baseline:
- Commit: 3019eba
- Message: feat: implement frozen Sentinel contracts
- 114 tests passing
- main pushed successfully
- working tree clean
- Transaction contract is V1.1 domain-scoped CNP e-commerce contract
- Fact and all remaining frozen contracts are implemented and tested

NOW IMPLEMENT ONLY THE NEXT BUILD CHECKPOINT:

# CHECKPOINT: Synthetic Transaction Generator

Reference contracts already implemented in:
- shared/contracts/transaction.py
- shared/contracts/case.py
- shared/contracts/detection.py
- shared/contracts/fact.py
- shared/contracts/evidence.py
- shared/contracts/reasoning.py
- shared/contracts/policy.py
- shared/contracts/tools.py
- shared/contracts/events.py

Reference specifications:
- Sentinel_V1_Build_Architecture_v1.1.md
- Sentinel_Technical_Design_Contracts_v1.1_FINAL_FROZEN-1.md
- build.md
- rules.md

IMPORTANT:
Do NOT modify existing frozen contracts unless an actual compile/test failure proves it is necessary.
Do NOT implement detection, Evidence Agent, Gemini reasoning, robustness, policy, Firestore persistence, Pub/Sub, BigQuery, analyst UI, or deployment in this checkpoint.
This checkpoint is ONLY the synthetic transaction generator.

## 1. Domain constraints

Generate ONLY V1 transactions:

- payment_rail = CARD_CNP
- direction = OUTGOING
- authorization_stage = PRE_AUTH
- card_present = false
- channel = WEB or MOBILE

Entities represented by the Transaction contract:
- customer
- account
- card/payment instrument
- merchant
- device
- IP/location

Do not generate UPI, IMPS, NEFT, RTGS, ATM, incoming/receiving-side transactions, or other out-of-scope flows.

Every generated transaction MUST validate successfully against the existing Transaction Pydantic model.

## 2. Generator design

Create a deterministic, seedable synthetic transaction generator under an appropriate location, preferably:

shared/generator/

Use a clean separation between:
- entity/profile generation
- transaction generation
- seeded scenario generation

The generator must support:
- configurable random seed
- configurable number of transactions
- reproducible output for the same seed
- realistic but synthetic data
- UTC timestamps
- Decimal transaction amounts
- valid currency
- valid enum values
- valid geo coordinates
- stable IDs linking related transactions to the same customer/account/card/merchant/device

Do NOT use external APIs or real customer data.

## 3. Normal baseline data

Generate realistic normal customer behavior, including variation in:
- transaction amount
- merchant
- merchant category
- timestamp
- device
- IP/location
- WEB/MOBILE channel

The data should not be uniformly random nonsense.

Create customer profiles so that repeated transactions from the same customer establish a meaningful behavioral baseline.

For example, a customer may normally:
- transact from a familiar device
- transact from a familiar geography
- transact within a normal amount range
- transact during a normal time window
- use a small set of merchants/categories

The exact synthetic distributions are implementation decisions, but keep them explainable and deterministic.

## 4. Required seeded anomaly scenarios

The generator MUST support deterministic seeded scenarios that will later be consumed by the detection layer.

At minimum provide explicit scenarios for:

1. NEW_DEVICE
2. UNUSUAL_LOCATION
3. UNUSUAL_AMOUNT
4. UNUSUAL_TIME
5. IMPOSSIBLE_TRAVEL
6. MERCHANT_RISK
7. LINKED_ENTITY_ANOMALY
8. KYC_ANOMALY

Do NOT implement detection logic here.

The generator's responsibility is simply to create transactions/profiles whose data can later produce those anomaly conditions.

Where useful, expose scenario metadata separately from the Transaction object so tests and future evaluation code can identify what was intentionally seeded.

Do not put artificial anomaly tags into Transaction itself.

## 5. Mandatory Sentinel demo scenario

Create one deterministic flagship scenario matching the V1.1 architecture:

- NEW_DEVICE
- UNUSUAL_LOCATION
- MERCHANT_RISK

It must also contain the branching hook required by the architecture:

The seeded device must have evidence indicating that the same device is associated with another account/customer so that later:

NEW_DEVICE
→ get_device_history
→ discovers device relationship
→ Evidence Agent independently chooses get_linked_entities

The generator does NOT implement the Evidence Agent.

It only needs to generate the underlying synthetic entities/data necessary for this later branch.

Make this scenario easy to invoke by name, for example:

seeded_demo_case()

or an equivalent clean API.

## 6. Data quality requirements

Ensure:
- IDs are unique where they should be unique.
- Related entities reuse IDs correctly.
- No accidental duplicate transaction IDs.
- timestamps are timezone-aware UTC.
- amount is Decimal.
- geo lat/lon are valid.
- currency is valid.
- all enum values come from existing contracts.
- all generated transactions pass Pydantic validation.
- no real PII.
- no secrets.
- no external network dependency.

Do not overengineer this.

## 7. Tests

Create focused tests under:

tests/generator/

Test at minimum:

1. Generated transaction validates against Transaction.
2. Same seed produces identical generated dataset.
3. Different seeds produce different datasets.
4. Requested transaction count is respected.
5. Transaction IDs are unique.
6. Required V1 domain fields are always correct.
7. Amounts are Decimal.
8. timestamps are UTC/timezone-aware.
9. geo values are valid.
10. customer/account/card relationships are consistent.
11. normal baseline scenario is reproducible.
12. each required seeded scenario is reproducible.
13. flagship demo scenario contains:
    - new device relationship
    - unusual location setup
    - merchant-risk setup
    - cross-account/device relationship needed for later branching

Do NOT test detection tags because detection is not implemented yet.

## 8. API quality

Provide a small, clean public API from the generator package.

Prefer something conceptually like:

generate_transactions(...)
generate_scenario(...)
seeded_demo_case(...)

Use type hints and concise docstrings.

Do not expose unnecessary implementation details.

## 9. Verification

After implementation:

1. Run all tests:
   pytest

2. Run compile verification:
   python -m compileall shared tests

3. Run a small generator smoke test.

4. Inspect the generated output and verify it conforms to the V1.1 Transaction contract.

5. Verify the flagship demo scenario manually from the generated data.

6. Run:
   git status
   git diff --stat
   git diff

Do not modify unrelated files.

## 10. Git discipline

After all tests and verification pass:

- Stage ONLY files belonging to this Synthetic Transaction Generator checkpoint.
- Do not stage .env, credentials, .venv, caches, IDE files, temporary files, or generated datasets unless a small fixture is intentionally required by tests.
- Do not amend previous commits.
- Do not force push.

Commit with EXACT message:

feat: add synthetic transaction generator

Then push:

git push origin main

Finally verify:

git status
git log -2 --oneline

## FINAL REPORT

Return a concise report containing:

A. Files created/modified
B. Generator capabilities
C. Seeded scenarios implemented
D. Flagship demo scenario verification
E. Test result
F. Compile result
G. Commit hash
H. Push result
I. Final git status
J. Any issues

Do not claim anything as complete unless it was actually verified.