# Sentinel Analyst UI

The Build Checklist Phase 5 analyst console -- Case Queue and Case Detail --
implementing the approved "Evidence Ledger" design specification. React +
TypeScript, Tailwind v4 (custom design tokens only, see `src/index.css`),
Radix UI primitives.

## Run locally

The backend (`services/api/main.py`) must be running first:

```
# from the repo root
python -m uvicorn services.api.main:app --reload
```

Then, from this directory:

```
npm install
npm run dev
```

The dev server proxies to `http://localhost:8000` by default (see
`VITE_API_BASE_URL` in `.env.example`).

## Scripts

- `npm run dev` -- local dev server
- `npm run build` -- typecheck + production build
- `npm run lint` -- oxlint
- `npm run test` -- vitest

## Data

Every screen reads the real `GET /cases`, `GET /cases/{case_id}`, and
`POST /cases/{case_id}/decision` endpoints (`services/api/cases.py`,
Build Checklist Phase 5.1) -- no mocked production data. `src/lib/types.ts`
mirrors the backend's real Pydantic contracts field-for-field.
