# Sentinel

## Real-Time AI Fraud Investigation & Case Intelligence

Sentinel is an AI-assisted fraud investigation system for outgoing card-not-present (CNP) e-commerce transactions at the pre-authorization stage. It combines deterministic anomaly detection, an agentic evidence-gathering workflow, Gemini-based structured reasoning, decision robustness analysis, and a deterministic policy service to investigate suspicious transactions, then hands escalated cases to a human analyst through a dedicated review UI.

**Governing safety principle (frozen, never weakened):**

> Probabilistic AI investigates and reasons. Deterministic policy controls automated disposition. Humans retain authority over blocking and overrides.

Gemini never approves, declines, blocks, releases, or finalizes a disposition. The deterministic Policy service can only ever emit `AUTO_RESOLVE` or `ESCALATE` -- it can never produce `BLOCK_HOLD`. Only a human analyst, through `POST /cases/{case_id}/decision`, can execute `BLOCK_HOLD`.

## V1 Architecture

```text
Transaction
    ↓
Detection (deterministic anomaly scoring)
    ↓
Evidence Agent (Gemini Flash, agentic tool use)
    ↓
Gemini Reasoning (Gemini Pro, structured findings)
    ↓
Decision Robustness (fast-path estimate + live counterfactual)
    ↓
Deterministic Policy (AUTO_RESOLVE / ESCALATE only)
    ↓
Firestore
    ↓
Analyst UI (Firebase-authenticated human review)
```

One Cloud Run service hosts both the FastAPI backend and the compiled React analyst UI -- no separate frontend hosting, no event bus, no second datastore. Firestore is V1's sole persistence layer.

## V1 scope

**Built:** CNP e-commerce, outgoing, pre-authorization fraud investigation for a single payment rail. Detection → Evidence Agent → Reasoning → Robustness → Policy → human review, end to end, with real Gemini and real Firestore, no mocked production behavior.

**Explicitly not built in V1** (see `.claude/skills/sentinel-engineering/SKILL.md` for the full list, and the frozen Contracts §34 "Build/Don't-Build boundary"): other payment rails (UPI, IMPS/NEFT/RTGS, ATM, incoming-side fraud), RAG/precedent retrieval, BigQuery, a Pub/Sub event backbone, multi-service topology, an `ADMIN` role, an analyst-management UI, a manual case claim/release workflow, real KYC/merchant API integrations, or a fine-tuned/custom model.

## Synthetic / mock data vs. production data

**There is no live production fraud feed, and no connection to any real banking, customer, or merchant system.** `POST /transactions` (`shared/pipeline/orchestrator.py:resolve_scenario_for_transaction`) first tries to match the submitted `transaction_id` against a committed seed scenario (`data/seed/scenarios/`) with mocked customer/merchant/device history. A `transaction_id` matching none of them is **not rejected**: `shared/generator/synthesis.py` deterministically synthesizes a plausible customer/merchant investigation context from the transaction's own identifiers (stable `hashlib.sha256`-derived seeds -- the same identifiers always produce the same synthetic context, in any process), and the real submitted transaction is investigated through the exact same pipeline. This lets the judge-facing Transaction Console accept any valid transaction document matching the supported schema, not only the five pre-committed demo scenarios. "Unknown transaction" never means "automatic fraud" or "automatic clean" -- Detection, Evidence Agent, Reasoning, Robustness, and Policy alone determine the outcome; the context resolver never computes or implies a disposition. The Detection model is trained on a public, synthetic/anonymized credit-card fraud dataset (`data/raw/`, not committed to this repo -- see `data/raw/README.md`), evaluated on a genuine held-out split. Every Gemini call (Evidence Agent, Reasoning, live counterfactual) is real, not mocked; every Firestore read/write is real. Only the underlying transaction/customer/merchant data itself is synthetic/demo data.

## Authentication

Analysts sign in with Firebase email/password (`ui/src/lib/auth.tsx`). The backend never trusts a client-supplied identity: every protected `/cases*` request must carry a real `Authorization: Bearer <Firebase ID token>` header, which `shared/auth/dependencies.py` verifies server-side via the Firebase Admin SDK, then resolves against a Sentinel-controlled analyst directory (Firestore `analysts/{uid}`, seeded operationally by `scripts/seed_analyst_directory.py` -- there is no analyst-management UI in V1). An authenticated-but-unregistered Firebase user is rejected (403).

Exactly two roles exist, always resolved server-side, never client-supplied: `ANALYST` (can `CLEAR`, `BLOCK_HOLD`, `ESCALATE_SENIOR`) and `SENIOR_ANALYST` (can `CLEAR`, `BLOCK_HOLD`, but not escalate further -- this prevents escalation loops). There is no `ADMIN` role.

**Demo accounts** (seeded via `scripts/seed_analyst_directory.py`, password `SentinelDemo!2026` -- disclosed here deliberately, since these are non-production demo credentials, not a real secret being exposed):

| Email | Role |
|---|---|
| `analyst1@sentinel.demo` | ANALYST |
| `analyst2@sentinel.demo` | ANALYST |
| `senior1@sentinel.demo` | SENIOR_ANALYST |

`GET /cases` has no global queue -- it always returns only cases where `assigned_analyst_id` equals the authenticated caller's Firebase UID. Cases are assigned by deterministic round-robin (active `ANALYST`s only) the moment a case first enters `HUMAN_REVIEW`; escalating to a senior directly reassigns `assigned_analyst_id` and never re-triggers round-robin.

## Local setup

### Prerequisites

- Python 3.13, Node 22
- `gcloud auth application-default login` (Application Default Credentials -- Sentinel never reads an API key; Vertex AI, Firestore, and Firebase Admin token verification all authenticate via ADC)
- Access to the `sentinel-ai-builder-cup` GCP project (Vertex AI, Firestore, and Firebase Auth already provisioned there), or your own project with the same APIs enabled and `.env` pointed at it

### Backend setup

```bash
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env  # defaults already match sentinel-ai-builder-cup
uvicorn services.api.main:app --reload --port 8000
```

`GET /` is the health check. `POST /transactions` runs the full pipeline (no auth -- it is the pipeline's ingestion endpoint, not an analyst-facing one). `GET /cases`, `GET /cases/{case_id}`, `POST /cases/{case_id}/decision` all require a Firebase ID token.

### Frontend setup

```bash
cd ui
npm install
cp .env.example .env  # optional -- real defaults are already baked in
npm run dev  # http://localhost:5173, proxies API calls to VITE_API_BASE_URL
```

Sign in with one of the demo accounts above.

### Seeding the analyst directory (one-time, per Firestore project)

```bash
python -m scripts.seed_analyst_directory
```

## Running tests

```bash
# Backend: everything except real-GCP integration tests
pytest --ignore-glob="*_live.py" --ignore=tests/data/test_trained_model.py

# Backend: including real Gemini/Firestore/Firebase Auth integration
# (requires ADC and the seeded analyst directory above)
pytest

# Frontend
cd ui
npm run lint
npm run build   # tsc -b && vite build
npm run test    # vitest run
```

CI (`.github/workflows/ci.yml`) runs the credential-free backend subset plus the full frontend job on every push/PR -- it never provisions GCP credentials, matching V1's "minimal CI" scope. The `*_live.py` files and `scripts/run_*.py`/`scripts/evaluate_*.py` evaluation scripts are how real-Gemini/Firestore/Firebase correctness is actually proven (see `eval/*.json` for the resulting artifacts); that proof happens outside CI, against real infrastructure, not by mocking it away.

## Deployment

One container, one Cloud Run service, built from the repo root `Dockerfile` (a multi-stage build: the React UI is compiled first, then copied into the Python/FastAPI image so one process serves both):

```bash
gcloud run deploy sentinel-v1 \
  --source . \
  --region us-central1 \
  --project sentinel-ai-builder-cup \
  --service-account sentinel-cloud-run@sentinel-ai-builder-cup.iam.gserviceaccount.com \
  --allow-unauthenticated
```

`sentinel-cloud-run` is least-privilege (`roles/aiplatform.user`, `roles/datastore.user` only -- never Owner/Editor). The service is network-public (`--allow-unauthenticated`) because a real analyst's browser has no GCP identity token to present at the Cloud Run layer -- Firebase Auth, enforced inside every `/cases*` endpoint, is the actual access boundary, not IAM. `POST /transactions` has no Firebase-Auth gate (it is the pipeline's system-level ingestion endpoint, not an analyst action); it is otherwise unauthenticated by design in V1, the same way it was before the analyst UI existed.

Firestore Security Rules (`firestore.rules`, deny-all for every direct client read/write -- the backend's Admin SDK is Firestore's only writer; the browser only ever talks to Firestore through this API) are deployed via the Firebase Rules API, not just committed as a file -- re-deploy after any change:

```bash
# see the Firebase Rules REST API (firebaserules.googleapis.com) -- create a
# ruleset from firestore.rules, then release it to the (default) database.
```

## Safety boundary (frozen, see `shared/contracts/` and the ten Safety Invariants)

1. Gemini cannot directly execute an action.
2. Policy cannot produce `BLOCK_HOLD` or `AUTO_DECLINE` -- its `PolicyOutcome` enum has no such members.
3. Only a human analyst, through `POST /cases/{case_id}/decision`, can execute `BLOCK_HOLD`.
4. Partial required evidence cannot auto-resolve.
5. Every automated Policy decision records `rule_id` + `rule_version`.
6. Every material reasoning factor is traceable to a specific evidence `fact_id`.
7. Duplicate request delivery cannot create duplicate cases or side effects (Firestore-transactional idempotency).
8. A request that exhausts its bounded retries fails safe to `ESCALATE`/`HUMAN_REVIEW`, never a silent drop or auto-resolve.
9. Human decisions are first-valid-decision-wins: a Firestore transaction re-verifies eligibility at write time, so two concurrent decisions on the same case can never both apply, and a finalized case's disposition can never be overwritten by a later, different decision.
10. `GET /cases` and `GET /cases/{case_id}` are scoped to the authenticated caller's own assigned cases -- there is no global queue and no way to view a case that is not yours.
