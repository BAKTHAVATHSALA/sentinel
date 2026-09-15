"""The single pipeline entry point for Sentinel V1 (Contracts V1-Scoped S19,
Build Checklist Phase 4.3):

    POST /transactions
      -> Detection()
      -> (if flagged) EvidenceAgent()
      -> Reasoning()
      -> RobustnessScorer() [fast-path, the default for every investigated case]
      -> Policy()
      -> Firestore write

Clean/normal transactions (zero anomaly_tags) skip investigation entirely
and resolve immediately -- Evidence Agent, Reasoning, Robustness Scorer, and
Policy are never invoked for them, matching the checklist's explicit
"skip investigation entirely" requirement (not just "skip Evidence Agent").

Fixture-backed transaction resolution: V1 has no live customer/merchant data
source (Contracts V1-Scoped S10 "all tools are read-only, mocked against
seeded fixture data"). This orchestrator resolves the customer/merchant/
baseline-transaction context a transaction needs by matching its
transaction_id against the committed seed scenarios (data/seed/scenarios/).
This is what lets Build Checklist Phase 4.3's "run all seeded scenarios
through the full pipeline" be a literal HTTP call with that scenario's own
target_transaction as the request body.

Idempotency (Safety Invariants 8/9): a transaction_id that already has a
case is never re-run -- the existing case is returned as-is.

Fail-safe (Contracts V1-Scoped S22, Safety Invariant 10): any unhandled
exception during the flagged-case pipeline aborts the request, forces the
case to ESCALATED with an audit note, and re-raises so the caller gets a
clear error -- it never leaves a case in a dangling, half-written state.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid

from shared.contracts.case import CaseState
from shared.contracts.detection import DetectionOutput
from shared.contracts.evidence import EvidenceAgentInput, EvidenceCompleteness
from shared.contracts.events import ActorType, AuditEvent
from shared.contracts.reasoning import ReasoningInput, ReasoningStatus
from shared.contracts.transaction import Transaction
from shared.detection import detect_transaction
from shared.evidence.agent import EvidenceAgent, EvidenceAgentModelClient
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.generator.models import ScenarioResult
from shared.generator.seed_loader import load_all_scenarios
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


def resolve_scenario_for_transaction(transaction_id: str) -> ScenarioResult:
    """Resolve the seeded scenario whose target_transaction matches transaction_id.

    :param transaction_id: transaction_id from the incoming request.
    :return: The matching ScenarioResult.
    :raises UnknownTransactionError: if no seeded scenario has this transaction_id.
    """
    for scenario in load_all_scenarios().values():
        if scenario.target_transaction.transaction_id == transaction_id:
            return scenario
    raise UnknownTransactionError(
        f"transaction_id '{transaction_id}' matches no seeded scenario -- V1 has no live "
        "customer/merchant data source (Contracts V1-Scoped S10)."
    )


def run_pipeline(
    transaction: Transaction,
    case_store: CaseStore | None = None,
    evidence_client: EvidenceAgentModelClient | None = None,
    reasoning_client: ReasoningModelClient | None = None,
) -> dict[str, object]:
    """Run the full Sentinel V1 pipeline for one transaction and return a result summary.

    :param transaction: The Transaction to investigate (POST /transactions body).
    :param case_store: Injected CaseStore; defaults to a real Firestore-backed store.
    :param evidence_client: Injected Evidence Agent Gemini client; defaults to real Vertex AI.
    :param reasoning_client: Injected Reasoning Gemini client; defaults to real Vertex AI.
    :return: {"case_id", "transaction_id", "state", "outcome", "rule_id"} summary.
    :raises UnknownTransactionError: if transaction_id matches no seeded scenario.
    """
    store = case_store or CaseStore(build_firestore_client())
    transaction_id = transaction.transaction_id

    existing_case_id = store.get_case_id_for_transaction(transaction_id)
    if existing_case_id is not None:
        _log(existing_case_id, transaction_id, "Duplicate POST /transactions -- returning existing case")
        existing = store.get_case(existing_case_id) or {}
        return {
            "case_id": existing_case_id,
            "transaction_id": transaction_id,
            "state": existing.get("state"),
            "outcome": (existing.get("policy_decision") or {}).get("outcome"),
            "rule_id": (existing.get("policy_decision") or {}).get("rule_id"),
            "duplicate": True,
        }

    scenario = resolve_scenario_for_transaction(transaction_id)
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
        return {
            "case_id": resolved_case_id,
            "transaction_id": transaction_id,
            "state": existing.get("state"),
            "outcome": (existing.get("policy_decision") or {}).get("outcome"),
            "rule_id": (existing.get("policy_decision") or {}).get("rule_id"),
            "duplicate": True,
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
        return _resolve_clean_transaction(store, case_id, transaction_id, now)

    try:
        return _investigate_flagged_transaction(
            store, case_id, transaction, detection, scenario, evidence_client, reasoning_client
        )
    except Exception as exc:  # noqa: BLE001 -- Contracts V1-Scoped S22: any unhandled failure must fail safe to ESCALATED
        _log(case_id, transaction_id, f"Unhandled exception during investigation: {exc!r} -- forcing ESCALATED")
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
        raise


def _resolve_clean_transaction(
    store: CaseStore, case_id: str, transaction_id: str, now: datetime
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
    }


def _investigate_flagged_transaction(
    store: CaseStore,
    case_id: str,
    transaction: Transaction,
    detection: DetectionOutput,
    scenario: ScenarioResult,
    evidence_client: EvidenceAgentModelClient | None,
    reasoning_client: ReasoningModelClient | None,
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

    final_state = CaseState.AUTO_RESOLVED if policy_decision.outcome.value == "AUTO_RESOLVE" else CaseState.ESCALATED
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
    _log(case_id, transaction_id, f"Pipeline complete: final_state={final_state.value}")

    return {
        "case_id": case_id,
        "transaction_id": transaction_id,
        "state": final_state.value,
        "outcome": policy_decision.outcome.value,
        "rule_id": policy_decision.rule_id,
        "duplicate": False,
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
