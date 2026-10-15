"""Sentinel Demo Mode API for hackathon judges.

Allows judges to explore Sentinel end-to-end without credentials, while strictly
preserving all production security, Firebase authentication, authorization,
and deterministic policy safety guarantees.

Every demo read, mutation, and reset is strictly scoped to the caller's verified
server-issued session capability. Production cases and audit logs are never touched.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from services.api.cases import (
    CounterfactualResult,
    DecisionResponse,
    QueueCaseSummary,
    _compute_counterfactual,
    _to_queue_summary,
    get_reasoning_client,
)
from shared.contracts.case import CaseState, HumanAction
from shared.contracts.events import ActorType, AuditEvent
from shared.demo.fixtures import SAMPLE_CLEAN_TRANSACTION, SAMPLE_HIGH_RISK_TRANSACTION
from shared.demo.rate_limiter import demo_rate_limiter
from shared.demo.session import (
    DemoSessionClaims,
    create_demo_session_token,
    verify_demo_session_token,
)
from shared.demo.store import DemoStore
from shared.reasoning.service import ReasoningModelClient

router = APIRouter(prefix="/demo", tags=["demo"])

# Module-level singleton demo store, overridable in tests via dependency injection
_demo_store = DemoStore()


def get_demo_store() -> DemoStore:
    """FastAPI dependency for DemoStore; overridable in tests."""
    return _demo_store


def _get_client_ip(request: Request) -> str:
    """Extract client IP with trusted proxy header awareness."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Leftmost entry is the originating client IP
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def get_current_demo_session(
    request: Request,
    authorization: str | None = Header(default=None),
    x_sentinel_demo_session: str | None = Header(default=None),
) -> DemoSessionClaims:
    """FastAPI dependency: strictly validates the server-issued capability token.

    A client-supplied session ID alone never grants access. The token must be an
    active, cryptographically valid HMAC token issued by this server.
    """
    client_ip = _get_client_ip(request)

    # 1. Enforce global and per-IP rate limits before processing
    demo_rate_limiter.check_global_limit()
    demo_rate_limiter.check_ip_limit(client_ip)

    token = x_sentinel_demo_session
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[len("Bearer ") :].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing demo session capability token. Please start a demo session first.",
        )

    claims = verify_demo_session_token(token)
    if claims is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired demo session capability. Please start a new demo session.",
        )

    return claims


class DemoSessionResponse(BaseModel):
    """Response returned when a demo session is bootstrapped."""

    model_config = ConfigDict(extra="forbid")

    session_token: str
    session_id: str
    expires_at: int
    display_name: str
    role: str


DEMO_SENIORS = [
    {"uid": "senior_demo_01", "display_name": "Elena Cho (Senior Fraud Analyst)", "email": "elena.cho@sentinel.demo"},
    {"uid": "senior_demo_02", "display_name": "Marcus Vance (Lead Risk Officer)", "email": "marcus.vance@sentinel.demo"},
]


class DemoDecisionRequest(BaseModel):
    """Payload for submitting a human analyst decision on a demo case."""

    model_config = ConfigDict(extra="ignore")

    case_id: str
    action: HumanAction
    reason: str = Field(min_length=1, max_length=500)
    evidence_acknowledged: bool
    target_analyst_id: str | None = None
    analyst_id: str | None = None
    client_timestamp: datetime | str | None = None


@router.post("/session")
def create_session(request: Request, store: DemoStore = Depends(get_demo_store)) -> DemoSessionResponse:
    """Bootstrap an isolated demo session for a judge.

    Issues a high-entropy signed capability token and initializes the 10 pre-seeded
    synthetic demo cases for that session.
    """
    client_ip = _get_client_ip(request)
    demo_rate_limiter.check_global_limit()
    demo_rate_limiter.check_session_creation_limit(client_ip)

    token, claims = create_demo_session_token()
    store.init_session(claims.session_id)

    return DemoSessionResponse(
        session_token=token,
        session_id=claims.session_id,
        expires_at=claims.expires_at,
        display_name=claims.display_name,
        role=claims.role,
    )


@router.get("/session")
def get_session(session: DemoSessionClaims = Depends(get_current_demo_session)) -> DemoSessionClaims:
    """Validate and return active demo session status."""
    return session


@router.get("/sample-transactions")
def get_sample_transactions() -> dict[str, object]:
    """Provide pre-packaged clean and high-risk synthetic transactions for 1-click execution."""
    return {
        "clean": SAMPLE_CLEAN_TRANSACTION.model_dump(mode="json"),
        "high_risk": SAMPLE_HIGH_RISK_TRANSACTION.model_dump(mode="json"),
    }


@router.get("/cases")
def list_demo_cases(
    response: Response,
    scope: str | None = Query(default=None),
    session: DemoSessionClaims = Depends(get_current_demo_session),
    store: DemoStore = Depends(get_demo_store),
) -> list[QueueCaseSummary]:
    """List the 10 pre-seeded demo cases for this session.

    Strictly scoped to session.session_id. Returns server-resolved demo analyst
    headers for persistent navigation.
    """
    response.headers["X-Analyst-Display-Name"] = session.display_name
    response.headers["X-Analyst-Role"] = session.role

    documents = store.list_cases(session.session_id)
    if scope != "dashboard":
        # Only open cases in HUMAN_REVIEW
        open_cases = [d for d in documents if d.get("state") == CaseState.HUMAN_REVIEW.value]
        return [_to_queue_summary(doc) for doc in open_cases]

    # Dashboard scope: return all cases for metrics (open + finalized)
    return [_to_queue_summary(doc) for doc in documents]


@router.get("/cases/{case_id}")
def get_demo_case(
    case_id: str,
    request: Request,
    response: Response,
    simulate_without: str | None = Query(default=None),
    session: DemoSessionClaims = Depends(get_current_demo_session),
    store: DemoStore = Depends(get_demo_store),
    reasoning_client: ReasoningModelClient = Depends(get_reasoning_client),
) -> dict[str, object]:
    """Full demo case detail with strict ownership verification.

    Attempts to read production cases or another judge's cases return 404 Not Found.
    `?simulate_without=<fact_id>` executes live counterfactual re-evaluations under
    strict rate limits and in-flight concurrency locks.
    """
    response.headers["X-Analyst-Display-Name"] = session.display_name
    response.headers["X-Analyst-Role"] = session.role

    document = store.get_case(session.session_id, case_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    document = dict(document)

    if simulate_without:
        client_ip = _get_client_ip(request)
        demo_rate_limiter.check_counterfactual_limit(session.session_id, client_ip)
        demo_rate_limiter.acquire_counterfactual_in_flight(session.session_id)
        try:
            document["counterfactual"] = _compute_counterfactual(document, simulate_without, reasoning_client)
        finally:
            demo_rate_limiter.release_counterfactual_in_flight(session.session_id)

    # In demo mode, expose mock senior analyst options if case is in HUMAN_REVIEW
    if document.get("state") == CaseState.HUMAN_REVIEW.value and not document.get("is_escalated"):
        document["available_seniors"] = DEMO_SENIORS
    else:
        document["available_seniors"] = []

    return document


@router.post("/cases/{case_id}/decision")
def post_demo_decision(
    case_id: str,
    request_body: DemoDecisionRequest,
    session: DemoSessionClaims = Depends(get_current_demo_session),
    store: DemoStore = Depends(get_demo_store),
) -> DecisionResponse:
    """Record a human decision on a demo case.

    Supported decisions in Demo Mode are CLEAR, BLOCK_HOLD, and ESCALATE_SENIOR.
    """
    if request_body.case_id != case_id:
        raise HTTPException(
            status_code=400,
            detail=f"Path case_id '{case_id}' does not match body case_id '{request_body.case_id}'",
        )

    if not request_body.evidence_acknowledged:
        raise HTTPException(
            status_code=400,
            detail="evidence_acknowledged must be true before a decision can be recorded",
        )

    reason = request_body.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail="A non-empty reason is required before a decision can be recorded",
        )

    document = store.get_case(session.session_id, case_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    decided_at = datetime.now(timezone.utc)

    if request_body.action == HumanAction.ESCALATE_SENIOR:
        target_uid = request_body.target_analyst_id
        if not target_uid:
            raise HTTPException(
                status_code=400,
                detail="A target senior analyst must be selected for escalation.",
            )
        senior_match = next((s for s in DEMO_SENIORS if s["uid"] == target_uid), None)
        target_display_name = senior_match["display_name"] if senior_match else "Elena Cho (Senior Fraud Analyst)"

        updates = {
            "state": CaseState.HUMAN_REVIEW.value,
            "assigned_analyst_id": target_uid,
            "target_analyst_display_name": target_display_name,
            "is_escalated": True,
            "escalated_reason": reason,
            "updated_at": decided_at,
        }

        audit_event = AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=str(document.get("transaction_id", "")),
            event_type="ESCALATE_SENIOR",
            actor_type=ActorType.HUMAN,
            actor_id="demo_analyst",
            output_snapshot={
                "action": "ESCALATE_SENIOR",
                "reason": reason,
                "evidence_acknowledged": True,
                "is_demo": True,
                "target_analyst_id": target_uid,
                "target_analyst_display_name": target_display_name,
                "session_id": session.session_id,
            },
            occurred_at=decided_at,
        )
    else:
        updates = {
            "state": CaseState.FINALIZED.value,
            "updated_at": decided_at,
            "final_disposition": request_body.action.value,
            "final_reason": reason,
        }

        audit_event = AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=str(document.get("transaction_id", "")),
            event_type="FINALIZED",
            actor_type=ActorType.HUMAN,
            actor_id="demo_analyst",
            output_snapshot={
                "action": request_body.action.value,
                "reason": reason,
                "evidence_acknowledged": True,
                "is_demo": True,
                "session_id": session.session_id,
            },
            occurred_at=decided_at,
        )

    outcome, current_doc = store.apply_decision(
        session_id=session.session_id,
        case_id=case_id,
        action=request_body.action.value,
        reason=reason,
        updates=updates,
        audit_event=audit_event,
    )

    if outcome == "not_found":
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    if outcome == "conflict":
        raise HTTPException(
            status_code=409,
            detail="This case was already finalized or escalated by another decision; first valid decision wins.",
        )

    return DecisionResponse(
        case_id=case_id,
        state=current_doc.get("state", CaseState.FINALIZED.value),
        final_disposition=current_doc.get("final_disposition"),
        assigned_analyst_id=current_doc.get("assigned_analyst_id", "demo_analyst"),
        target_analyst_display_name=current_doc.get("target_analyst_display_name"),
        decided_at=decided_at,
        idempotent_replay=(outcome == "idempotent"),
    )


@router.post("/reset")
def reset_demo_session(
    request: Request,
    session: DemoSessionClaims = Depends(get_current_demo_session),
    store: DemoStore = Depends(get_demo_store),
) -> dict[str, str]:
    """Atomically restore the 10 demo cases for this session to their pristine initial states.

    Protected by debounce and rate limiting. Has zero impact on other judges' sessions.
    """
    client_ip = _get_client_ip(request)
    demo_rate_limiter.check_reset_limit(session.session_id, client_ip)

    store.reset_session(session.session_id)
    return {"status": "ok", "message": "Demo session reset to initial state"}
