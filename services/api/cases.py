"""Case API for the Sentinel V1 analyst UI (Build Checklist Phase 5.1,
Contracts V1-Scoped S23.1).

GET /cases                     -- queue view: cases awaiting human review
GET /cases/{case_id}           -- full case detail
POST /cases/{case_id}/decision -- human decision (CLEAR | BLOCK_HOLD | ESCALATE_SENIOR)

Every response is projected directly from the real cases/{case_id} document
(shared/persistence/case_document.py) -- no field here is invented; the
queue summary only narrows which of the document's own fields are returned.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from shared.contracts.case import CaseState, HumanAction
from shared.contracts.events import ActorType, AuditEvent
from shared.contracts.policy import HumanDecisionRequest
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client

router = APIRouter()


def get_case_store() -> CaseStore:
    """FastAPI dependency: the real Firestore-backed CaseStore.

    Overridden in tests via app.dependency_overrides to inject a fake store.
    """
    return CaseStore(build_firestore_client())


class QueueCaseSummary(BaseModel):
    """One row of the Build Checklist Phase 5.1/5.2 queue view -- risk band and
    robustness flag visible without opening the case, projected from the stored
    case document's own transaction/detection/robustness fields."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    transaction_id: str
    state: str
    created_at: datetime
    updated_at: datetime
    amount: str
    currency: str
    merchant_id: str
    risk_band: str
    anomaly_tags: list[str]
    robustness_classification: str | None
    robustness_fragile_factor_id: str | None


def _to_queue_summary(document: dict[str, object]) -> QueueCaseSummary:
    transaction = document.get("transaction") or {}
    detection = document.get("detection") or {}
    robustness = document.get("robustness") or {}
    return QueueCaseSummary(
        case_id=document["case_id"],
        transaction_id=document["transaction_id"],
        state=document["state"],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
        amount=transaction.get("amount", "0"),
        currency=transaction.get("currency", ""),
        merchant_id=transaction.get("merchant_id", ""),
        risk_band=detection.get("risk_band", ""),
        anomaly_tags=detection.get("anomaly_tags", []),
        robustness_classification=robustness.get("classification"),
        robustness_fragile_factor_id=robustness.get("fragile_factor_id"),
    )


@router.get("/cases")
def list_cases(store: CaseStore = Depends(get_case_store)) -> list[QueueCaseSummary]:
    """Queue view: every case currently awaiting human review.

    Build Checklist Phase 5.1: "GET /cases (queue view -- escalated cases only,
    with risk band and robustness flag)". A case is in this list exactly when
    Policy escalated it and it has not yet been finalized by an analyst.
    """
    documents = store.list_cases_by_state(CaseState.HUMAN_REVIEW.value)
    return [_to_queue_summary(doc) for doc in documents]


@router.get("/cases/{case_id}")
def get_case(case_id: str, store: CaseStore = Depends(get_case_store)) -> dict[str, object]:
    """Full case detail: the raw cases/{case_id} document, unmodified."""
    document = store.get_case(case_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    return document


class DecisionResponse(BaseModel):
    """Confirmation returned after a human decision is recorded."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    state: str
    final_disposition: str
    decided_at: datetime
    idempotent_replay: bool


@router.post("/cases/{case_id}/decision")
def post_decision(
    case_id: str, request: HumanDecisionRequest, store: CaseStore = Depends(get_case_store)
) -> DecisionResponse:
    """Record a human analyst's final decision on an escalated case.

    Enforces (Build Checklist Phase 5.1): the case must be in HUMAN_REVIEW state;
    `reason` is required for BLOCK_HOLD and ESCALATE_SENIOR; the action is
    idempotent (Contracts V1-Scoped S20 decision-level idempotency); a decision
    always writes an audit event. Only this endpoint can ever produce BLOCK_HOLD
    (Safety Invariant 4) -- Policy (shared/policy/evaluator.py) can never reach it.
    """
    if request.case_id != case_id:
        raise HTTPException(
            status_code=400,
            detail=f"Path case_id '{case_id}' does not match request body case_id '{request.case_id}'",
        )

    document = store.get_case(case_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    if document["state"] == CaseState.FINALIZED.value:
        # Decision-level idempotency (Contracts V1-Scoped S20): a duplicate
        # decision submission returns the existing outcome rather than
        # re-applying or erroring.
        return DecisionResponse(
            case_id=case_id,
            state=document["state"],
            final_disposition=document.get("final_disposition") or "",
            decided_at=document["updated_at"],
            idempotent_replay=True,
        )

    if document["state"] != CaseState.HUMAN_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail=f"Case '{case_id}' is in state '{document['state']}', not HUMAN_REVIEW",
        )

    if request.action in (HumanAction.BLOCK_HOLD, HumanAction.ESCALATE_SENIOR) and not request.reason:
        raise HTTPException(
            status_code=400,
            detail=f"A reason is required for action '{request.action.value}'",
        )

    if not request.evidence_acknowledged:
        raise HTTPException(
            status_code=400,
            detail="evidence_acknowledged must be true before a decision can be recorded",
        )

    decided_at = datetime.now(timezone.utc)
    store.update_case(
        case_id,
        {
            "state": CaseState.FINALIZED.value,
            "updated_at": decided_at,
            "final_disposition": request.action.value,
            "assigned_analyst_id": request.analyst_id,
        },
    )
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=document["transaction_id"],
            event_type="FINALIZED",
            actor_type=ActorType.HUMAN,
            actor_id=request.analyst_id,
            output_snapshot={
                "action": request.action.value,
                "reason": request.reason,
                "evidence_acknowledged": request.evidence_acknowledged,
            },
            occurred_at=decided_at,
        ),
    )

    return DecisionResponse(
        case_id=case_id,
        state=CaseState.FINALIZED.value,
        final_disposition=request.action.value,
        decided_at=decided_at,
        idempotent_replay=False,
    )
