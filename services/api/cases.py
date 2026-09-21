"""Case API for the Sentinel V1 analyst UI (Build Checklist Phase 5.1,
Contracts V1-Scoped S23.1, V1 Authoritative Ruling + Addendum 1).

GET /cases                     -- queue view: cases assigned to the caller
GET /cases/{case_id}           -- full case detail (+ optional counterfactual)
POST /cases/{case_id}/decision -- human decision (CLEAR | BLOCK_HOLD | ESCALATE_SENIOR)

Every response is projected directly from the real cases/{case_id} document
(shared/persistence/case_document.py) -- no field here is invented; the
queue summary only narrows which of the document's own fields are returned.
Every endpoint requires a verified Firebase ID token (shared/auth) and is
scoped to the authenticated caller -- there is no global queue in V1.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict

from shared.auth.dependencies import get_analyst_directory, get_current_analyst
from shared.auth.directory import AnalystDirectory
from shared.auth.models import AnalystRole, AuthenticatedAnalyst
from shared.contracts.case import CaseState, HumanAction
from shared.contracts.detection import DetectionOutput
from shared.contracts.evidence import EvidenceBundle
from shared.contracts.events import ActorType, AuditEvent
from shared.contracts.policy import HumanDecisionRequest
from shared.contracts.reasoning import ReasoningInput, ReasoningOutput, ReasoningStatus
from shared.contracts.transaction import Transaction
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client
from shared.policy.evaluator import evaluate_policy
from shared.reasoning.gemini_client import VertexReasoningClient
from shared.reasoning.prompt import PROMPT_VERSION
from shared.reasoning.service import ReasoningModelClient, ReasoningService
from shared.robustness.scorer import RobustnessScorer

router = APIRouter()


def get_case_store() -> CaseStore:
    """FastAPI dependency: the real Firestore-backed CaseStore.

    Overridden in tests via app.dependency_overrides to inject a fake store.
    """
    return CaseStore(build_firestore_client())


def get_reasoning_client() -> ReasoningModelClient:
    """FastAPI dependency: the real Vertex AI Reasoning client, used only by the
    live counterfactual query parameter. Overridden in tests."""
    return VertexReasoningClient()


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
    final_disposition: str | None = None
    is_escalated_by_me: bool = False


def _to_queue_summary(document: dict[str, object], *, is_escalated_by_me: bool = False) -> QueueCaseSummary:
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
        final_disposition=document.get("final_disposition"),
        is_escalated_by_me=is_escalated_by_me,
    )


@router.get("/cases")
def list_cases(
    response: Response,
    scope: str | None = Query(default=None),
    caller: AuthenticatedAnalyst = Depends(get_current_analyst),
    store: CaseStore = Depends(get_case_store),
) -> list[QueueCaseSummary]:
    """Queue view: cases in HUMAN_REVIEW assigned to the authenticated caller.

    V1 Authoritative Ruling Part 6: "GET /cases must be scoped to
    assigned_analyst_id == authenticated caller's Firebase UID -- there is NO
    global analyst queue in V1." A senior analyst sees exactly the cases
    escalated to them; an analyst sees exactly the cases round-robin assigned
    to them. AUTO_RESOLVE/FINALIZED cases are never returned here (state filter).

    Response headers X-Analyst-Display-Name/X-Analyst-Role additively expose
    the already-server-resolved caller identity (never client-supplied) so
    the frontend's persistent nav bar can render it without a new endpoint or
    a breaking change to this endpoint's existing array response body.

    `?scope=dashboard` additively broadens this same response for the
    dashboard metric cards, without a new endpoint: omitting `scope` (every
    existing caller) returns byte-identical output to before. With
    `scope=dashboard`, the response is the union of three still-caller-scoped
    queries -- this analyst's own HUMAN_REVIEW cases, this analyst's own
    FINALIZED cases, and cases this analyst escalated via ESCALATE_SENIOR
    (`escalated_by_analyst_id == caller.uid`, regardless of who holds it now)
    -- each row's `is_escalated_by_me` says which bucket it came from, so the
    frontend never has to compare raw UIDs (and this endpoint never returns
    another analyst's escalation history: the escalated-by query is always
    filtered to the caller's own UID, never a collection-group query).
    """
    response.headers["X-Analyst-Display-Name"] = caller.display_name
    response.headers["X-Analyst-Role"] = caller.role.value

    if scope != "dashboard":
        documents = store.list_cases_by_state_and_assigned_analyst(CaseState.HUMAN_REVIEW.value, caller.uid)
        return [_to_queue_summary(doc) for doc in documents]

    own_open = store.list_cases_by_state_and_assigned_analyst(CaseState.HUMAN_REVIEW.value, caller.uid)
    own_closed = store.list_cases_by_state_and_assigned_analyst(CaseState.FINALIZED.value, caller.uid)
    escalated_by_me = store.list_cases_by_escalated_by(caller.uid)

    own_case_ids = {doc["case_id"] for doc in own_open} | {doc["case_id"] for doc in own_closed}
    summaries = [_to_queue_summary(doc, is_escalated_by_me=False) for doc in (*own_open, *own_closed)]
    summaries += [
        _to_queue_summary(doc, is_escalated_by_me=True) for doc in escalated_by_me if doc["case_id"] not in own_case_ids
    ]
    return summaries


class SeniorOption(BaseModel):
    """One escalation-target option for the UI's senior-selection dropdown
    (V1 Authoritative Ruling Part 4: "show senior name/email, raw UID NOT
    shown" -- the UID here is a transport value for target_analyst_id, never
    rendered as visible dropdown text)."""

    model_config = ConfigDict(extra="forbid")

    uid: str
    display_name: str
    email: str


class CounterfactualResult(BaseModel):
    """Response-only, non-persisted counterfactual re-evaluation (Addendum 1
    Point 4 / mega-prompt Section 9): present only when `simulate_without` is
    supplied."""

    model_config = ConfigDict(extra="forbid")

    removed_fact_id: str
    findings: dict[str, object] | None
    robustness: dict[str, object]
    policy_outcome_would_change: bool


@router.get("/cases/{case_id}")
def get_case(
    case_id: str,
    response: Response,
    simulate_without: str | None = Query(default=None),
    caller: AuthenticatedAnalyst = Depends(get_current_analyst),
    store: CaseStore = Depends(get_case_store),
    directory: AnalystDirectory = Depends(get_analyst_directory),
    reasoning_client: ReasoningModelClient = Depends(get_reasoning_client),
) -> dict[str, object]:
    """Full case detail: the raw cases/{case_id} document, unmodified, scoped to
    the authenticated caller (V1 Authoritative Ruling Part 6 -- "do not expose
    arbitrary cases merely because the user is authenticated").

    A case that doesn't exist and a case that exists but isn't assigned to
    the caller return the IDENTICAL 404 response (same status, same detail
    text) -- deliberately consistent so neither the frontend nor an external
    observer can distinguish "no such case" from "exists but not yours" (a
    resource-enumeration side channel otherwise). The underlying ownership
    rule is unchanged; only the two failure responses were made
    indistinguishable.

    `?simulate_without=<fact_id>` additively attaches a fresh, non-persisted
    `counterfactual` field (mega-prompt Section 9/10): rebuilds the evidence
    bundle without that fact, re-invokes Reasoning for real, and reports
    whether Policy's outcome would change. Never written to Firestore.

    When the case is in HUMAN_REVIEW and the caller is an ANALYST, the
    response additively includes `available_seniors` (name/email options for
    the UI's escalation dropdown, mega-prompt Section G.5) -- not a fifth
    endpoint, reusing this same already-fetched case detail response.

    Response headers X-Analyst-Display-Name/X-Analyst-Role -- see list_cases.
    """
    response.headers["X-Analyst-Display-Name"] = caller.display_name
    response.headers["X-Analyst-Role"] = caller.role.value

    document = store.get_case(case_id)
    case_not_available = HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    if document is None:
        raise case_not_available

    if document.get("assigned_analyst_id") != caller.uid:
        raise case_not_available

    document = dict(document)

    if simulate_without:
        document["counterfactual"] = _compute_counterfactual(document, simulate_without, reasoning_client)

    if document.get("state") == CaseState.HUMAN_REVIEW.value and caller.role == AnalystRole.ANALYST:
        document["available_seniors"] = [
            SeniorOption(uid=r.uid, display_name=r.display_name, email=r.email).model_dump(mode="json")
            for r in directory.list_active_seniors()
        ]

    return document


def _compute_counterfactual(
    document: dict[str, object], fact_id_to_remove: str, reasoning_client: ReasoningModelClient
) -> dict[str, object]:
    evidence_bundle_data = document.get("evidence_bundle")
    if not evidence_bundle_data:
        raise HTTPException(status_code=400, detail="This case has no evidence bundle to simulate against")

    evidence_bundle = EvidenceBundle.model_validate(evidence_bundle_data)
    if fact_id_to_remove not in {fact.fact_id for fact in evidence_bundle.facts}:
        raise HTTPException(status_code=404, detail=f"fact_id '{fact_id_to_remove}' is not part of this case's evidence")

    transaction = Transaction.model_validate(document["transaction"])
    detection = DetectionOutput.model_validate(document["detection"])
    reasoning_input = ReasoningInput(
        case_id=document["case_id"],
        transaction=transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        prompt_version=PROMPT_VERSION,
    )

    reasoning_service = ReasoningService(reasoning_client)
    scorer = RobustnessScorer(reasoning_service)
    robustness_result, counterfactual_findings = scorer.live_counterfactual_with_findings(
        document["case_id"], reasoning_input, fact_id_to_remove
    )

    original_outcome = (document.get("policy_decision") or {}).get("outcome")
    policy_outcome_would_change = False
    if counterfactual_findings is not None:
        counterfactual_reasoning_output = ReasoningOutput(
            status=ReasoningStatus.SUCCESS,
            findings=counterfactual_findings,
            attempts=1,
            failure_reasons=[],
            model_name=counterfactual_findings.model_name,
            model_version=counterfactual_findings.model_version,
        )
        counterfactual_decision = evaluate_policy(
            case_id=document["case_id"],
            transaction=transaction,
            detection=detection,
            evidence_bundle=evidence_bundle,
            reasoning_output=counterfactual_reasoning_output,
        )
        policy_outcome_would_change = counterfactual_decision.outcome.value != original_outcome

    return CounterfactualResult(
        removed_fact_id=fact_id_to_remove,
        findings=counterfactual_findings.model_dump(mode="json") if counterfactual_findings else None,
        robustness=robustness_result.model_dump(mode="json"),
        policy_outcome_would_change=policy_outcome_would_change,
    ).model_dump(mode="json")


class DecisionResponse(BaseModel):
    """Confirmation returned after a human decision is recorded.

    `target_analyst_display_name` is additive (Q11 verification, same
    non-breaking pattern as the Addendum 1 Point 4 `counterfactual`
    addition): populated only for a successful ESCALATE_SENIOR, from the
    same directory record already fetched and validated earlier in
    post_decision -- so the frontend's escalation confirmation screen can
    show a name instead of the raw `assigned_analyst_id` UID, without a
    second lookup and without ever calling GET /cases/{case_id}.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    state: str
    final_disposition: str | None
    assigned_analyst_id: str | None
    decided_at: datetime
    idempotent_replay: bool
    target_analyst_display_name: str | None = None


REASON_REQUIRED_ACTIONS = (HumanAction.CLEAR, HumanAction.BLOCK_HOLD, HumanAction.ESCALATE_SENIOR)


@router.post("/cases/{case_id}/decision")
def post_decision(
    case_id: str,
    request: HumanDecisionRequest,
    caller: AuthenticatedAnalyst = Depends(get_current_analyst),
    store: CaseStore = Depends(get_case_store),
    directory: AnalystDirectory = Depends(get_analyst_directory),
) -> DecisionResponse:
    """Record a human analyst's final decision on an escalated case, or reassign
    it to a senior analyst (V1 Authoritative Ruling Parts 3/4/7/8).

    Enforces: the caller must be the case's current assigned_analyst_id; a
    reason is mandatory for all three actions; only an ANALYST may
    ESCALATE_SENIOR (a SENIOR_ANALYST cannot escalate further); the selected
    escalation target must be a currently active SENIOR_ANALYST; decisions are
    applied through a Firestore transaction enforcing first-valid-decision-wins
    (a duplicate identical request is idempotent, a conflicting later request
    on an already-decided case is rejected). Only this endpoint can ever
    produce BLOCK_HOLD (Safety Invariant 4) -- Policy (shared/policy/evaluator.py)
    can never reach it.
    """
    if request.case_id != case_id:
        raise HTTPException(
            status_code=400,
            detail=f"Path case_id '{case_id}' does not match request body case_id '{request.case_id}'",
        )

    if request.analyst_id != caller.uid:
        raise HTTPException(status_code=403, detail="analyst_id does not match the authenticated caller")

    document = store.get_case(case_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    # ESCALATE_SENIOR changes assigned_analyst_id, so a duplicate retry of an
    # analyst's own already-applied escalation legitimately arrives after
    # ownership has already moved to the target senior -- that idempotency
    # check belongs to the transaction below (store.apply_human_decision),
    # not this pre-check. CLEAR/BLOCK_HOLD never change ownership, so the
    # caller must currently own the case to finalize (or idempotently
    # re-finalize) it.
    if request.action != HumanAction.ESCALATE_SENIOR and document.get("assigned_analyst_id") != caller.uid:
        raise HTTPException(status_code=403, detail="This case is not assigned to you")

    if request.action in REASON_REQUIRED_ACTIONS and not (request.reason and request.reason.strip()):
        raise HTTPException(status_code=400, detail=f"A reason is required for action '{request.action.value}'")

    if not request.evidence_acknowledged:
        raise HTTPException(
            status_code=400,
            detail="evidence_acknowledged must be true before a decision can be recorded",
        )

    target_analyst_id: str | None = None
    target_analyst_display_name: str | None = None
    if request.action == HumanAction.ESCALATE_SENIOR:
        if caller.role == AnalystRole.SENIOR_ANALYST:
            raise HTTPException(status_code=403, detail="A senior analyst cannot escalate further")
        if not request.target_analyst_id:
            raise HTTPException(status_code=400, detail="target_analyst_id is required for ESCALATE_SENIOR")
        target_record = directory.get(request.target_analyst_id)
        if target_record is None or target_record.role != AnalystRole.SENIOR_ANALYST or not target_record.active:
            raise HTTPException(status_code=400, detail="target_analyst_id must be a currently active senior analyst")
        target_analyst_id = target_record.uid
        target_analyst_display_name = target_record.display_name

    decided_at = datetime.now(timezone.utc)
    reason = (request.reason or "").strip()

    if request.action == HumanAction.ESCALATE_SENIOR:
        # `escalated_by_analyst_id` is historical attribution only (dashboard
        # metrics), derived exclusively from the verified caller identity --
        # never client-supplied, never read from the request body. It is set
        # once, here, and never overwritten again (a SENIOR_ANALYST can never
        # reach this branch -- see the role check above -- so a case can be
        # escalated at most once). `assigned_analyst_id` still changes to the
        # selected senior exactly as before; this field does not participate
        # in any authorization or assignment decision.
        updates: dict[str, object] = {
            "assigned_analyst_id": target_analyst_id,
            "escalated_by_analyst_id": caller.uid,
            "updated_at": decided_at,
        }
        event_type = "ESCALATED_TO_SENIOR"
    else:
        updates = {
            "state": CaseState.FINALIZED.value,
            "updated_at": decided_at,
            "final_disposition": request.action.value,
            "final_reason": reason,
        }
        event_type = "FINALIZED"

    audit_event = AuditEvent(
        audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
        case_id=case_id,
        transaction_id=document["transaction_id"],
        event_type=event_type,
        actor_type=ActorType.HUMAN,
        actor_id=caller.uid,
        output_snapshot={
            "action": request.action.value,
            "reason": reason,
            "evidence_acknowledged": request.evidence_acknowledged,
            "target_analyst_id": target_analyst_id,
        },
        occurred_at=decided_at,
    )

    outcome, current_document = store.apply_human_decision(
        case_id=case_id,
        caller_uid=caller.uid,
        action=request.action.value,
        reason=reason,
        target_analyst_id=target_analyst_id,
        updates=updates,
        audit_event=audit_event,
    )

    if outcome == "not_found":
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    if outcome == "conflict":
        store.append_audit_event(
            case_id,
            AuditEvent(
                audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
                case_id=case_id,
                transaction_id=document["transaction_id"],
                event_type="DECISION_REJECTED_CONFLICT",
                actor_type=ActorType.HUMAN,
                actor_id=caller.uid,
                output_snapshot={"attempted_action": request.action.value, "current_state": current_document.get("state")},
                occurred_at=decided_at,
            ),
        )
        raise HTTPException(
            status_code=409,
            detail="This case was already decided or reassigned by another request; first valid decision wins",
        )

    return DecisionResponse(
        case_id=case_id,
        state=current_document.get("state", ""),
        final_disposition=current_document.get("final_disposition"),
        assigned_analyst_id=current_document.get("assigned_analyst_id"),
        decided_at=decided_at,
        idempotent_replay=(outcome == "idempotent"),
        target_analyst_display_name=target_analyst_display_name,
    )
