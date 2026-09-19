"""Sentinel V1's single Cloud Run service entry point (Contracts V1-Scoped
S23, Build Checklist Phase 4.3/4.4/5.1).

`POST /transactions` is the full pipeline entry point (Phase 4.3). `GET
/cases`, `GET /cases/{case_id}`, and `POST /cases/{case_id}/decision` (Phase
5.1, the analyst UI's backend) are registered from services/api/cases.py.
`GET /api/health` is the liveness/readiness probe. `GET /` and every other
unmatched path serve the compiled React SPA (mega-prompt Section 12: the
bare Cloud Run URL must show the analyst login page, not a JSON payload).
Deliberately not `/healthz`: on this project's `*.run.app` domain, Google's
own front-end infrastructure intercepts the exact literal path `/healthz`
before it ever reaches the container (verified live: `/healthz` -> Google's
generic 404 page; `/healthz/` and `/Healthz` both reach this app normally)
-- `/api/health` avoids that reserved convention entirely.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from services.api.cases import router as cases_router
from shared.contracts.events import ErrorEnvelope
from shared.contracts.transaction import Transaction
from shared.pipeline.orchestrator import UnknownTransactionError, run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("sentinel.api")

app = FastAPI(title="Sentinel V1", description="Fraud investigation pipeline -- V1 prototype")

# The analyst UI (Build Checklist Phase 5) is a separate Vite dev server in
# local development, proxying to this API on a different origin/port; in
# production (mega-prompt Section 12) the compiled UI is served by this same
# Cloud Run container, same-origin, so CORS does not apply there at all --
# this middleware exists only for `npm run dev`.
app.add_middleware(
    CORSMiddleware,
    # 5173 is Vite's documented default (README "Frontend setup"); 5180 is
    # this machine's actual local dev port because 5173/5174 were already
    # bound by another process when this session started `npm run dev`.
    # Same pattern as the existing two entries -- no wildcard, no new
    # configurability introduced (no CORS-origin env var exists in
    # .env.example to reuse).
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5180",
        "http://127.0.0.1:5180",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(cases_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe. Deliberately not at "/" -- mega-prompt
    Section 12 requires the bare Cloud Run URL to serve the compiled React
    SPA (the analyst login page), not a JSON health payload. Also
    deliberately not at "/healthz": verified live that Google's front-end
    infrastructure intercepts that exact literal path on this service's
    `*.run.app` domain before it ever reaches this container (a 404 from
    Google, not from this app). Cloud Run's own startup probe for this
    service is a plain TCP check on $PORT (verified via
    `gcloud run services describe`), not an HTTP path, so this route's
    location has no deployment-config dependency."""
    return {"service": "sentinel-v1", "status": "ok"}


@app.post("/transactions")
def post_transactions(transaction: Transaction) -> dict[str, object]:
    """Run the full Sentinel V1 pipeline for one transaction.

    Detection -> (if flagged) Evidence Agent -> Reasoning -> Robustness
    Scorer -> Policy -> Firestore write. Clean transactions (no anomaly
    tags) resolve immediately without investigation. A transaction_id that
    already has a case returns the existing case instead of re-running the
    pipeline (Safety Invariants 8/9).
    """
    try:
        return run_pipeline(transaction)
    except UnknownTransactionError as exc:
        logger.info(f"transaction_id={transaction.transaction_id} - {exc}")
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 -- Contracts V1-Scoped S22: return a clear error to the caller
        logger.exception(f"transaction_id={transaction.transaction_id} - Unhandled pipeline failure")
        envelope = ErrorEnvelope(
            error_code="PIPELINE_UNHANDLED_EXCEPTION",
            message=str(exc),
            retryable=False,
            transaction_id=transaction.transaction_id,
            occurred_at=datetime.now(timezone.utc),
        )
        return JSONResponse(status_code=500, content=envelope.model_dump(mode="json"))


# Compiled React UI (mega-prompt Section 12: "serve compiled frontend from
# the same FastAPI/Cloud Run container"). ui/dist is absent in local `pytest`/
# `uvicorn --reload` dev workflows (the UI runs on its own Vite dev server
# instead) -- static/catch-all routes are only registered when a real build
# exists, so nothing here breaks local development or the test suite. This
# block is deliberately the last thing registered: the catch-all path route
# (including the bare "/") must never shadow a real API route above it
# (/api/health, /cases, /cases/{id}, /cases/{id}/decision, /transactions --
# FastAPI/Starlette match routes in registration order, not by specificity).
_UI_DIST = Path(__file__).resolve().parent.parent.parent / "ui" / "dist"

if _UI_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_UI_DIST / "assets"), name="ui-assets")

    @app.get("/{full_path:path}")
    def serve_ui(full_path: str) -> FileResponse:
        """SPA fallback: "/" and any path not matched by an API route above is
        a client-side React Router route (/, /login, /case/{id}, ...) -- serve
        index.html and let the browser-side router take over. A path matching
        a real built asset file (under /assets, mounted separately above) is
        served directly instead."""
        candidate = _UI_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_UI_DIST / "index.html")
