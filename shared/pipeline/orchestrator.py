"""The single pipeline entry point for Sentinel V1 (Contracts V1-Scoped S19,
Build Checklist Phase 4.3):

    POST /transactions
      -> Detection()
      -> (if flagged) EvidenceAgent()
      -> Reasoning()
      -> RobustnessScorer() [fast-path, the default for every investigated case]
      -> Policy()
      -> Firestore write

Clean transactions (zero anomaly_tags) always skip investigation entirely --
Evidence Agent, Reasoning, Robustness Scorer, and Policy are never invoked
for them, matching the checklist's explicit "skip investigation entirely"
requirement (not just "skip Evidence Agent"). The final disposition still
depends on risk_band, exactly as Rule P-004 (Contracts S16) has always
required alongside anomaly_tags = []: CLEAN + LOW resolves immediately
(AUTO_RESOLVED); CLEAN + MEDIUM/HIGH still skips investigation (there is
nothing to investigate) but reaches HUMAN_REVIEW instead, without ever
producing a PolicyDecision Policy did not actually evaluate.

Fixture-backed transaction resolution: V1 has no live customer/merchant data
source (Contracts V1-Scoped S10 "all tools are read-only, mocked against
seeded fixture data"). This orchestrator resolves the customer/merchant/
baseline-transaction context a transaction needs by matching its
transaction_id against the committed seed scenarios (data/seed/scenarios/)
first. This is what lets Build Checklist Phase 4.3's "run all seeded
scenarios through the full pipeline" be a literal HTTP call with that
scenario's own target_transaction as the request body.

A transaction_id matching no committed fixture is NOT rejected: it falls
through to shared/generator/synthesis.py, which deterministically
synthesizes a plausible customer/merchant context from the transaction's
own identifiers (still local, mocked data -- never a live external API,
so Contracts S10 still holds), and the real submitted transaction is
investigated through the exact same pipeline below. "Unknown transaction_id"
is not "automatic fraud" and not "reject the request" -- Detection,
Evidence Agent, Reasoning, Robustness, and Policy alone determine the
outcome, exactly as they do for a committed fixture.

Idempotency (Safety Invariants 8/9): a transaction_id that already has a
case is never re-run -- the existing case is returned as-is.

Fail-safe (Contracts V1-Scoped S22, Safety Invariant 10): any unhandled
exception during the flagged-case pipeline aborts the request, forces the
case to ESCALATED then HUMAN_REVIEW with an audit note, and re-raises so
the caller gets a clear error -- it never leaves a case in a dangling,
half-written state, and it never lands somewhere the analyst queue (GET
/cases, Build Checklist Phase 5.1) can't see it.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid

from shared.auth.assignment import AssignmentStore
from shared.auth.directory import AnalystDirectory
from shared.auth.models import AnalystRecord, AnalystRole
from shared.contracts.case import CaseState
from shared.contracts.detection import DetectionOutput, RiskBand
from shared.contracts.evidence import EvidenceAgentInput, EvidenceBundle, EvidenceCompleteness
from shared.contracts.events import ActorType, AuditEvent
from shared.contracts.policy import PolicyDecision
from shared.contracts.reasoning import CaseFindings, ReasoningInput, ReasoningStatus
from shared.contracts.transaction import Transaction
from shared.detection import detect_transaction
from shared.evidence.agent import EvidenceAgent, EvidenceAgentModelClient
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.generator.models import ScenarioResult
from shared.generator.seed_loader import load_all_scenarios
from shared.generator.synthesis import synthesize_scenario_for_transaction
from shared.persistence.case_document import build_case_document
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client
from shared.policy.evaluator import evaluate_policy
from shared.reasoning.gemini_client import VertexReasoningClient
from shared.reasoning.prompt import PROMPT_VERSION
from shared.reasoning.service import ReasoningModelClient, ReasoningService
from shared.robustness.scorer import RobustnessScorer

logger = logging.getLogger("sentinel.pipeline")


class UnknownTransactionError(Exception):
    """Raised when a transaction_id matches no seeded scenario -- V1 has no other
    fixture-backed data source to investigate against."""


def _log(case_id: str, transaction_id: str, message: str) -> None:
    logger.info(f"case_id={case_id} transaction_id={transaction_id} - {message}")


def _analyst_summary(record: AnalystRecord | None) -> dict[str, str] | None:
    """Judge-facing assignment summary for the public Transaction Console's
    POST /transactions response: display name only -- no email, no Firebase
    UID, no role. Additive response field, not a persisted document field,
    so no frozen contract changes (Addendum 1 Point 4 precedent for
    response-only additions).

    Restricted to the normal round-robin ANALYST pool only: a case whose
    current assigned_analyst_id belongs to a SENIOR_ANALYST (reached only
    through the existing, unchanged ESCALATE_SENIOR human-review workflow,
    never through this pipeline) must never be surfaced here as if it were
    a normal transaction-console assignment -- that identity is visible
    only inside the authenticated, case-scoped Analyst Portal.
    """
    if record is None or record.role != AnalystRole.ANALYST:
        return None
    return {"analyst_name": record.display_name}


def _decision_summary(
    detection: DetectionOutput,
    evidence_bundle: EvidenceBundle | None,
    findings: CaseFindings | None,
    policy_decision: PolicyDecision | None,
) -> dict[str, object]:
    """Public-safe decision summary for the Transaction Console: an
    additive POST /transactions response field (not a persisted document
    field -- Addendum 1 Point 4 precedent), so the public console can
    explain a result without GET /cases/{case_id} or any protected case
    content. Every value is read directly from the real pipeline objects
    already resolved during this request -- nothing here is computed,
    inferred, or invented for display purposes.

    Deliberately excluded (protected-case-only): raw evidence Facts,
    tools_called/agent_trace, findings.summary/supporting_factors/
    counter_factors/evidence_citations, robustness, exact merchant
    chargeback_rate/recent_fraud_report_count (only the boolean
    merchant_flagged), and anything identity-related (UID/email).

    :param detection: Always available (Detection always runs).
    :param evidence_bundle: None for a clean transaction that skipped investigation.
    :param findings: None if investigation was skipped, or if Reasoning failed.
    :param policy_decision: None if Policy was never invoked (clean transaction).
    :return: {"risk_assessment", "anomaly_tags", "policy_rule_id", "reasons",
        "evidence_completeness", "merchant_flagged"}.
    """
    anomaly_tags = [tag.value for tag in detection.anomaly_tags]
    risk_assessment = findings.risk_assessment.value if findings is not None else detection.risk_band.value
    return {
        "risk_assessment": risk_assessment,
        "anomaly_tags": anomaly_tags,
        "policy_rule_id": policy_decision.rule_id if policy_decision is not None else None,
        "reasons": list(policy_decision.reasons) if policy_decision is not None else [],
        "evidence_completeness": evidence_bundle.completeness.value if evidence_bundle is not None else None,
        "merchant_flagged": "MERCHANT_RISK" in anomaly_tags,
    }


def _decision_summary_from_document(document: dict[str, object]) -> dict[str, object]:
    """Same public-safe decision summary as _decision_summary, but sourced
    from an already-persisted Firestore case document (the duplicate-
    transaction return paths) instead of freshly-computed pipeline objects.
    Reads the same real, previously-computed fields verbatim -- it does not
    recompute or re-derive anything."""
    detection = document.get("detection") or {}
    evidence_bundle = document.get("evidence_bundle")
    findings = document.get("findings")
    policy_decision = document.get("policy_decision")

    anomaly_tags = list(detection.get("anomaly_tags") or [])
    risk_assessment = findings.get("risk_assessment") if findings else detection.get("risk_band")

    return {
        "risk_assessment": risk_assessment,
        "anomaly_tags": anomaly_tags,
        "policy_rule_id": policy_decision.get("rule_id") if policy_decision else None,
        "reasons": list(policy_decision.get("reasons") or []) if policy_decision else [],
        "evidence_completeness": evidence_bundle.get("completeness") if evidence_bundle else None,
        "merchant_flagged": "MERCHANT_RISK" in anomaly_tags,
    }


def resolve_scenario_for_transaction(transaction: Transaction) -> ScenarioResult:
    """Resolve the investigation context for a submitted transaction: a
    committed seed fixture if its transaction_id matches one exactly, or a
    deterministic synthetic context otherwise (shared/generator/synthesis.py).

    "Unknown transaction_id" no longer means "reject the request" -- every
    syntactically valid Transaction (already validated by the frozen
    contract before reaching here) can be investigated through the real
    pipeline. The seeded fixtures are matched first and never altered by
    this fallback; only a transaction_id absent from all of them falls
    through to synthesis.

    :param transaction: The submitted Transaction (POST /transactions body).
    :return: A ScenarioResult -- either an existing committed fixture, or a
        freshly synthesized one for this exact transaction.
    """
    for scenario in load_all_scenarios().values():
        if scenario.target_transaction.transaction_id == transaction.transaction_id:
            return scenario
    return synthesize_scenario_for_transaction(transaction)


def run_pipeline(
    transaction: Transaction,
    case_store: CaseStore | None = None,
    evidence_client: EvidenceAgentModelClient | None = None,
    reasoning_client: ReasoningModelClient | None = None,
    analyst_directory: AnalystDirectory | None = None,
    assignment_store: AssignmentStore | None = None,
) -> dict[str, object]:
    """Run the full Sentinel V1 pipeline for one transaction and return a result summary.

    :param transaction: The Transaction to investigate (POST /transactions body).
    :param case_store: Injected CaseStore; defaults to a real Firestore-backed store.
    :param evidence_client: Injected Evidence Agent Gemini client; defaults to real Vertex AI.
    :param reasoning_client: Injected Reasoning Gemini client; defaults to real Vertex AI.
    :param analyst_directory: Injected AnalystDirectory for round-robin assignment;
        defaults to a real Firestore-backed directory.
    :param assignment_store: Injected AssignmentStore for round-robin assignment;
        defaults to a real Firestore-backed store.
    :return: {"case_id", "transaction_id", "state", "outcome", "rule_id"} summary.
    """
    store = case_store or CaseStore(build_firestore_client())
    firestore_client = build_firestore_client() if (analyst_directory is None or assignment_store is None) else None
    directory = analyst_directory or AnalystDirectory(firestore_client)
    assignment = assignment_store or AssignmentStore(firestore_client)
    transaction_id = transaction.transaction_id

    existing_case_id = store.get_case_id_for_transaction(transaction_id)
    if existing_case_id is not None:
        _log(existing_case_id, transaction_id, "Duplicate POST /transactions -- returning existing case")
        existing = store.get_case(existing_case_id) or {}
        existing_assigned_uid = existing.get("assigned_analyst_id")
        return {
            "case_id": existing_case_id,
            "transaction_id": transaction_id,
            "state": existing.get("state"),
            "outcome": (existing.get("policy_decision") or {}).get("outcome"),
            "rule_id": (existing.get("policy_decision") or {}).get("rule_id"),
            "duplicate": True,
            "assignment": _analyst_summary(directory.get(existing_assigned_uid) if existing_assigned_uid else None),
            "decision_summary": _decision_summary_from_document(existing),
        }

    scenario = resolve_scenario_for_transaction(transaction)
    case_id = f"case_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    detection = detect_transaction(
        transaction=transaction,
        customer=scenario.customer_profile,
        history=list(scenario.baseline_transactions),
        merchant=scenario.merchant_profile,
        secondary_customer=scenario.secondary_profile,
        case_id=case_id,
    )
    _log(case_id, transaction_id, f"Detection complete: risk_band={detection.risk_band.value} anomaly_tags={[t.value for t in detection.anomaly_tags]}")

    document = build_case_document(
        case_id=case_id,
        transaction_id=transaction_id,
        state=CaseState.DETECTED,
        created_at=now,
        updated_at=now,
        transaction=transaction,
        detection=detection,
    )
    created, resolved_case_id = store.create_case_if_new(transaction_id, case_id, document)
    if not created:
        _log(resolved_case_id, transaction_id, "Lost the create race to a concurrent request -- returning its case")
        existing = store.get_case(resolved_case_id) or {}
        existing_assigned_uid = existing.get("assigned_analyst_id")
        return {
            "case_id": resolved_case_id,
            "transaction_id": transaction_id,
            "state": existing.get("state"),
            "outcome": (existing.get("policy_decision") or {}).get("outcome"),
            "rule_id": (existing.get("policy_decision") or {}).get("rule_id"),
            "duplicate": True,
            "assignment": _analyst_summary(directory.get(existing_assigned_uid) if existing_assigned_uid else None),
            "decision_summary": _decision_summary_from_document(existing),
        }

    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=transaction_id,
            event_type="CASE_DETECTED",
            actor_type=ActorType.SYSTEM,
            model_name=detection.model_name,
            model_version=detection.model_version,
            output_snapshot={"risk_band": detection.risk_band.value, "anomaly_tags": [t.value for t in detection.anomaly_tags]},
            occurred_at=now,
        ),
    )

    if not detection.anomaly_tags:
        # Rule P-004 (Contracts S16) has always required risk_score <= LOW
        # *alongside* anomaly_tags = [] for AUTO_RESOLVE -- a zero-anomaly-tag
        # transaction that Detection still scored MEDIUM/HIGH is CLEAN but not
        # LOW-risk, so it is not eligible for automatic resolution (business
        # rule: "CLEAN + LOW -> AUTO_RESOLVED"; MEDIUM/HIGH clean transactions
        # must reach a human). There is still nothing for the Evidence Agent
        # to investigate (zero anomaly tags), so Evidence/Reasoning/Robustness/
        # Policy are still never invoked for this case either way -- only the
        # final disposition differs based on risk_band.
        if detection.risk_band == RiskBand.LOW:
            return _resolve_clean_transaction(store, case_id, transaction_id, now, detection)
        return _escalate_clean_transaction_with_elevated_risk(
            store, case_id, transaction_id, now, detection, directory, assignment
        )

    try:
        return _investigate_flagged_transaction(
            store, case_id, transaction, detection, scenario, evidence_client, reasoning_client, directory, assignment
        )
    except Exception as exc:  # noqa: BLE001 -- Contracts V1-Scoped S22: any unhandled failure must fail safe to ESCALATED
        _log(case_id, transaction_id, f"Unhandled exception during investigation: {exc!r} -- forcing HUMAN_REVIEW")
        failure_time = datetime.now(timezone.utc)
        store.update_case(case_id, {"state": CaseState.ESCALATED.value, "updated_at": failure_time})
        store.append_audit_event(
            case_id,
            AuditEvent(
                audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
                case_id=case_id,
                transaction_id=transaction_id,
                event_type="PIPELINE_UNHANDLED_EXCEPTION",
                actor_type=ActorType.SYSTEM,
                output_snapshot={"error": repr(exc)},
                occurred_at=failure_time,
            ),
        )
        # Fail-safe still needs to reach a human queue, not just a resting
        # ESCALATED state the queue never queries (see the ESCALATE branch
        # above for why HUMAN_REVIEW, not ESCALATED, is what GET /cases lists).
        _transition_to_human_review(store, case_id, transaction_id, directory, assignment)
        raise


def _resolve_clean_transaction(
    store: CaseStore, case_id: str, transaction_id: str, now: datetime, detection: DetectionOutput
) -> dict[str, object]:
    _log(case_id, transaction_id, "No anomaly tags -- skipping investigation entirely, resolving immediately")
    resolved_at = datetime.now(timezone.utc)
    store.update_case(case_id, {"state": CaseState.AUTO_RESOLVED.value, "updated_at": resolved_at})
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=transaction_id,
            event_type="CLEAN_TRANSACTION_AUTO_RESOLVED",
            actor_type=ActorType.SYSTEM,
            output_snapshot={"reason": "no anomaly tags detected; investigation skipped"},
            occurred_at=resolved_at,
        ),
    )
    return {
        "case_id": case_id,
        "transaction_id": transaction_id,
        "state": CaseState.AUTO_RESOLVED.value,
        "outcome": None,
        "rule_id": None,
        "duplicate": False,
        "assignment": None,
        "decision_summary": _decision_summary(detection, None, None, None),
    }


def _escalate_clean_transaction_with_elevated_risk(
    store: CaseStore,
    case_id: str,
    transaction_id: str,
    now: datetime,
    detection: DetectionOutput,
    directory: AnalystDirectory,
    assignment: AssignmentStore,
) -> dict[str, object]:
    """A transaction with zero anomaly tags but a MEDIUM/HIGH risk_band: CLEAN
    but not LOW-risk, so (per Rule P-004's own long-standing risk_score <= LOW
    condition) it is not eligible for AUTO_RESOLVE. There is still nothing for
    the Evidence Agent to investigate -- zero anomaly tags means no evidence
    floor requires any tool call -- so Evidence/Reasoning/Robustness/Policy
    are not invoked, exactly as for the LOW-risk clean path. This mirrors the
    existing fail-safe path's pattern (above) of reaching HUMAN_REVIEW without
    ever producing a PolicyDecision, rather than fabricating one Policy never
    actually evaluated.
    """
    _log(
        case_id,
        transaction_id,
        f"No anomaly tags but risk_band={detection.risk_band.value} (not LOW) -- not eligible for auto-resolve, routing to human review without investigation",
    )
    escalate_time = datetime.now(timezone.utc)
    store.update_case(case_id, {"state": CaseState.ESCALATED.value, "updated_at": escalate_time})
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=transaction_id,
            event_type="ESCALATED",
            actor_type=ActorType.SYSTEM,
            output_snapshot={
                "reason": f"zero anomaly tags but risk_band={detection.risk_band.value} (not LOW); not eligible for auto-resolve"
            },
            occurred_at=escalate_time,
        ),
    )
    assignment_summary = _transition_to_human_review(store, case_id, transaction_id, directory, assignment)
    return {
        "case_id": case_id,
        "transaction_id": transaction_id,
        "state": CaseState.HUMAN_REVIEW.value,
        "outcome": None,
        "rule_id": None,
        "duplicate": False,
        "assignment": assignment_summary,
        "decision_summary": _decision_summary(detection, None, None, None),
    }


def _investigate_flagged_transaction(
    store: CaseStore,
    case_id: str,
    transaction: Transaction,
    detection: DetectionOutput,
    scenario: ScenarioResult,
    evidence_client: EvidenceAgentModelClient | None,
    reasoning_client: ReasoningModelClient | None,
    directory: AnalystDirectory,
    assignment: AssignmentStore,
) -> dict[str, object]:
    transaction_id = transaction.transaction_id

    _transition(store, case_id, transaction_id, CaseState.FLAGGED, "CASE_FLAGGED")
    _transition(store, case_id, transaction_id, CaseState.INVESTIGATING, "INVESTIGATION_STARTED")

    ctx = build_fixture_context(scenario, case_id=case_id)
    agent_input = EvidenceAgentInput(case_id=case_id, transaction=transaction, detection=detection)
    evidence_output = EvidenceAgent(evidence_client or VertexEvidenceAgentClient()).investigate(agent_input, ctx)
    evidence_bundle = evidence_output.evidence_bundle
    _log(case_id, transaction_id, f"Evidence Agent complete: completeness={evidence_bundle.completeness.value} tools_called={evidence_bundle.tools_called}")

    evidence_state = (
        CaseState.EVIDENCE_READY
        if evidence_bundle.completeness == EvidenceCompleteness.COMPLETE
        else CaseState.EVIDENCE_PARTIAL
    )
    now = datetime.now(timezone.utc)
    store.update_case(
        case_id,
        {"state": evidence_state.value, "updated_at": now, "evidence_bundle": evidence_bundle.model_dump(mode="json")},
    )
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=transaction_id,
            event_type=evidence_state.value,
            actor_type=ActorType.AGENT,
            model_name=evidence_output.model_name,
            model_version=evidence_output.model_version,
            output_snapshot={
                "completeness": evidence_bundle.completeness.value,
                "tools_called": evidence_bundle.tools_called,
            },
            occurred_at=now,
        ),
    )

    reasoning_input = ReasoningInput(
        case_id=case_id,
        transaction=transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        prompt_version=PROMPT_VERSION,
    )
    reasoning_service = ReasoningService(reasoning_client or VertexReasoningClient())
    reasoning_output = reasoning_service.reason(reasoning_input)
    _log(case_id, transaction_id, f"Reasoning complete: status={reasoning_output.status.value}")

    reasoning_state = CaseState.REASONED if reasoning_output.status == ReasoningStatus.SUCCESS else CaseState.REASONING_FAILED
    now = datetime.now(timezone.utc)
    findings_update: dict[str, object] = {"state": reasoning_state.value, "updated_at": now}
    if reasoning_output.findings is not None:
        findings_update["findings"] = reasoning_output.findings.model_dump(mode="json")
    store.update_case(case_id, findings_update)
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=transaction_id,
            event_type=reasoning_state.value,
            actor_type=ActorType.AGENT,
            model_name=reasoning_output.model_name,
            model_version=reasoning_output.model_version,
            output_snapshot={
                "status": reasoning_output.status.value,
                "risk_assessment": (
                    reasoning_output.findings.risk_assessment.value if reasoning_output.findings else None
                ),
            },
            occurred_at=now,
        ),
    )

    robustness_result = None
    if reasoning_output.status == ReasoningStatus.SUCCESS and reasoning_output.findings is not None:
        robustness_result = RobustnessScorer(reasoning_service).fast_path(case_id, reasoning_output.findings)
        _log(case_id, transaction_id, f"Robustness Scorer complete: classification={robustness_result.classification.value}")
        now = datetime.now(timezone.utc)
        store.update_case(case_id, {"updated_at": now, "robustness": robustness_result.model_dump(mode="json")})
        store.append_audit_event(
            case_id,
            AuditEvent(
                audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
                case_id=case_id,
                transaction_id=transaction_id,
                event_type="ROBUSTNESS_SCORED",
                actor_type=ActorType.SYSTEM,
                output_snapshot={"classification": robustness_result.classification.value, "method": robustness_result.method.value},
                occurred_at=now,
            ),
        )

    policy_decision = evaluate_policy(
        case_id=case_id,
        transaction=transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        reasoning_output=reasoning_output,
    )
    _log(case_id, transaction_id, f"Policy evaluated: rule_id={policy_decision.rule_id} outcome={policy_decision.outcome.value}")

    now = datetime.now(timezone.utc)
    store.update_case(
        case_id,
        {
            "state": CaseState.POLICY_EVALUATED.value,
            "updated_at": now,
            "policy_decision": policy_decision.model_dump(mode="json"),
        },
    )
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=transaction_id,
            event_type="POLICY_EVALUATED",
            actor_type=ActorType.SYSTEM,
            rule_id=policy_decision.rule_id,
            rule_version=policy_decision.rule_version,
            output_snapshot={"outcome": policy_decision.outcome.value, "reasons": policy_decision.reasons},
            occurred_at=now,
        ),
    )

    assignment_summary: dict[str, str] | None = None
    if policy_decision.outcome.value == "AUTO_RESOLVE":
        final_state = CaseState.AUTO_RESOLVED
        now = datetime.now(timezone.utc)
        store.update_case(case_id, {"state": final_state.value, "updated_at": now})
        store.append_audit_event(
            case_id,
            AuditEvent(
                audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
                case_id=case_id,
                transaction_id=transaction_id,
                event_type=final_state.value,
                actor_type=ActorType.SYSTEM,
                rule_id=policy_decision.rule_id,
                occurred_at=now,
            ),
        )
    else:
        # ESCALATE lands the case in HUMAN_REVIEW, not a resting ESCALATED
        # state: Build Checklist Phase 5.1 requires POST /cases/{case_id}/decision
        # to enforce "case must be in HUMAN_REVIEW state", and GET /cases's queue
        # view is exactly the set of cases awaiting that review. ESCALATED is
        # still recorded as its own audit-trail moment immediately before it.
        _transition(store, case_id, transaction_id, CaseState.ESCALATED, "ESCALATED")
        assignment_summary = _transition_to_human_review(store, case_id, transaction_id, directory, assignment)
        final_state = CaseState.HUMAN_REVIEW

    _log(case_id, transaction_id, f"Pipeline complete: final_state={final_state.value}")

    return {
        "case_id": case_id,
        "transaction_id": transaction_id,
        "state": final_state.value,
        "outcome": policy_decision.outcome.value,
        "rule_id": policy_decision.rule_id,
        "duplicate": False,
        "assignment": assignment_summary,
        "decision_summary": _decision_summary(detection, evidence_bundle, reasoning_output.findings, policy_decision),
    }


def _transition(store: CaseStore, case_id: str, transaction_id: str, state: CaseState, event_type: str) -> None:
    now = datetime.now(timezone.utc)
    store.update_case(case_id, {"state": state.value, "updated_at": now})
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=transaction_id,
            event_type=event_type,
            actor_type=ActorType.SYSTEM,
            occurred_at=now,
        ),
    )
    _log(case_id, transaction_id, f"State transition -> {state.value}")


def _transition_to_human_review(
    store: CaseStore,
    case_id: str,
    transaction_id: str,
    directory: AnalystDirectory,
    assignment: AssignmentStore,
) -> dict[str, str] | None:
    """Transition into HUMAN_REVIEW and fire deterministic round-robin
    assignment exactly once (V1 Authoritative Ruling Part 4/5): every code
    path that first enters HUMAN_REVIEW -- the normal ESCALATE outcome and the
    Contracts V1-Scoped S22 fail-safe path -- goes through this single
    function, so assignment can never fire twice for the same case and can
    never fire on a later ESCALATE_SENIOR reassignment (that is a direct
    assigned_analyst_id overwrite in services/api/cases.py, not a re-entry
    into HUMAN_REVIEW).

    :return: The judge-facing assignment summary (name/email) for whichever
        analyst was assigned, or None if the pool was empty -- reuses the
        active-analyst records already fetched below rather than issuing a
        second directory lookup.
    """
    active_records = directory.list_active_analysts()
    active_uids = [record.uid for record in active_records]
    assigned_uid = assignment.assign_next_analyst(active_uids)
    assigned_record = next((r for r in active_records if r.uid == assigned_uid), None) if assigned_uid else None

    now = datetime.now(timezone.utc)
    updates: dict[str, object] = {"state": CaseState.HUMAN_REVIEW.value, "updated_at": now}
    if assigned_uid is not None:
        updates["assigned_analyst_id"] = assigned_uid
    store.update_case(case_id, updates)

    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=transaction_id,
            event_type="HUMAN_REVIEW",
            actor_type=ActorType.SYSTEM,
            actor_id=assigned_uid,
            output_snapshot={"assigned_analyst_id": assigned_uid, "active_analyst_pool_size": len(active_uids)},
            occurred_at=now,
        ),
    )
    if assigned_uid is None:
        store.append_audit_event(
            case_id,
            AuditEvent(
                audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
                case_id=case_id,
                transaction_id=transaction_id,
                event_type="NO_ANALYST_AVAILABLE",
                actor_type=ActorType.SYSTEM,
                output_snapshot={"reason": "zero active analysts in round-robin pool; case left unassigned"},
                occurred_at=now,
            ),
        )
    _log(case_id, transaction_id, f"State transition -> HUMAN_REVIEW (assigned_analyst_id={assigned_uid})")
    return _analyst_summary(assigned_record)
