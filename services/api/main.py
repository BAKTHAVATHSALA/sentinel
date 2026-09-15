"""Sentinel V1's single Cloud Run service entry point (Contracts V1-Scoped
S23, Build Checklist Phase 4.3/4.4).

Only `POST /transactions` is implemented here -- the full pipeline entry
point. `GET /cases`, `GET /cases/{case_id}`, and `POST /cases/{case_id}/decision`
are Build Checklist Phase 5.1 deliverables (the analyst UI's backend) and are
deliberately not built in this phase.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from shared.contracts.events import ErrorEnvelope
from shared.contracts.transaction import Transaction
from shared.pipeline.orchestrator import UnknownTransactionError, run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("sentinel.api")

app = FastAPI(title="Sentinel V1", description="Fraud investigation pipeline -- V1 prototype")


@app.get("/")
def health() -> dict[str, str]:
    """Liveness/readiness probe for Cloud Run."""
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
