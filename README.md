# Sentinel

Sentinel is an AI-assisted fraud investigation system for card-not-present e-commerce transactions.

It goes beyond a risk score — Sentinel investigates a transaction, gathers relevant evidence, explains what it found, checks how robust the conclusion is, and routes the case through deterministic policy to either automatic resolution or human review.

## The problem

A fraud detection model can identify a transaction as unusual, but a score alone does not tell an analyst:

- Why the transaction is unusual
- What evidence supports or contradicts the signal
- Whether the conclusion depends heavily on one piece of evidence
- What should happen next

Sentinel focuses on this investigation layer — turning a transaction alert into an evidence-backed, reviewable case.

See [`docs/project.md`](docs/project.md) for the full problem statement and product direction.

## What it does

- **Detects** anomalies using a trained baseline risk model and transaction signals.
- **Investigates** flagged transactions by dynamically selecting relevant evidence sources.
- **Explains** findings with Gemini-based structured reasoning, including supporting factors, counter-evidence, and evidence gaps.
- **Stress-tests** conclusions through robustness analysis and live counterfactual investigation.
- **Routes** cases through deterministic policy rather than allowing the AI to make the final automated disposition.
- **Escalates** anomalous cases to human analysts for review and decision-making.
- **Audits** investigation and decision activity for traceability.

## How a transaction moves through the system

```text
Transaction
    ↓
Detection
    ↓
Evidence Investigation
    ↓
AI Reasoning
    ↓
Robustness Check
    ↓
Deterministic Policy
    ↓
Auto-Resolve / Human Review
```

**Governing principle:**

> AI investigates and reasons. Deterministic policy controls automated disposition. Humans retain authority over sensitive actions.

Escalated cases are assigned to an analyst and handled through the authenticated review workspace, with a senior-analyst escalation path when required.

## Current scope

V1 focuses on:

- Outgoing card-not-present e-commerce transactions
- Pre-authorization
- Customer, account, card, device, merchant, and location context

The risk model is trained on a public, anonymized credit-card fraud dataset. The investigation evidence currently comes from deterministic internal fixtures and synthetic context rather than live banking, KYC, merchant, or payment-network integrations.

Sentinel does not claim access to a real banking fraud database or external merchant fraud system.

See [`docs/architecture.md`](docs/architecture.md) for the architecture, scope boundaries, and evolution beyond V1.

## Beyond V1

The current prototype is intentionally focused on one transaction type. The architecture is designed to expand toward:

- Additional payment rails and transaction types
- Event-driven investigation at higher volume
- Richer production evidence sources
- Cross-transaction and fraud-ring analysis
- Historical case and investigation intelligence
- Production observability, governance, and security

The V1 → V2 evolution is described in [`docs/architecture.md`](docs/architecture.md).

## Tech stack

- **Backend:** Python, FastAPI, Pydantic
- **AI:** Gemini on Vertex AI
- **Risk model:** scikit-learn
- **Data:** Firestore
- **Authentication:** Firebase Authentication
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, React Router
- **Testing:** pytest, Vitest, Testing Library
- **Deployment:** Docker, Google Cloud Run

## Running locally

### Prerequisites

- Python 3.13
- Node.js 22
- Google Cloud Application Default Credentials

Authenticate with Google Cloud before running services that require Vertex AI, Firestore, or Firebase Admin:

```bash
gcloud auth application-default login
```

### Backend

From the repository root:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the backend environment file:

```bash
cp .env.example .env
```

Start the API:

```bash
uvicorn services.api.main:app --reload --port 8000
```

### Frontend

```bash
cd ui
npm install
cp .env.example .env
npm run dev
```

### Tests

Backend tests that do not require live GCP credentials or live model execution:

```bash
pytest --ignore-glob="*_live.py" --ignore=tests/data/test_trained_model.py
```

Frontend:

```bash
cd ui
npm run lint
npm run build
npm run test
```

## Configuration

Backend configuration is defined in:

```text
.env.example
```

Frontend configuration is defined in:

```text
ui/.env.example
```

Copy these files to their corresponding `.env` files for local development.

Do not commit credentials, private keys, or populated environment files.

## Deployment

Sentinel is packaged as a single container.

The root `Dockerfile` builds the React frontend and packages it with the FastAPI backend. The resulting application runs as a single Google Cloud Run service.

The exact container build and deployment configuration is maintained in the repository and deployment documentation.


## Documentation

- [`docs/project.md`](docs/project.md) — problem, purpose, product intent, and project direction
- [`docs/architecture.md`](docs/architecture.md) — system architecture and V1 → V2 evolution
- [`docs/ui.md`](docs/ui.md) — UI behavior and user experience
- [`docs/design-system.md`](docs/design-system.md) — visual design system and UI tokens
- [`docs/transaction_document_format.md`](docs/transaction_document_format.md) — transaction document format accepted by the public investigation console

## Status

Working prototype with:

- Public transaction-investigation console
- Firebase-authenticated analyst workspace
- AI-assisted investigation pipeline
- Deterministic policy routing
- Human analyst decision workflow
- Robustness and counterfactual analysis
- Automated backend and frontend testing
- Single-container Google Cloud Run deployment
