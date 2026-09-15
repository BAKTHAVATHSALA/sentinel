"""Seed one additional real case for the Build Checklist Phase 5 analyst UI's
REASONING_FAILED state.

The 5 Phase 1.4 scenarios (scripts/run_pipeline_scenarios.py) cover clean/
auto-resolved, escalated/robust, escalated/fragile, and partial-evidence
cases for real, because real Gemini reliably produces those outcomes for
those fixtures. Reasoning failure (two invalid/malformed structured-output
attempts in a row) is not something real Gemini can be reliably forced into
on demand -- so this script exercises the real pipeline building blocks
(Detection, the real Gemini Flash Evidence Agent, real Policy, real
Firestore) exactly as shared/pipeline/orchestrator.py does, substituting
only the Reasoning call with the same scripted-failure fake Gemini client
Phase 3/4's own test suite already uses to prove the fail-safe path
(tests/reasoning/test_service.py, tests/pipeline/test_orchestrator.py).
Nothing about the resulting case document is hand-authored -- every field
is produced by real system code.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid

from google.genai import types

from shared.contracts.case import CaseState
from shared.contracts.detection import DetectionOutput
from shared.contracts.evidence import EvidenceAgentInput, EvidenceCompleteness
from shared.contracts.events import ActorType, AuditEvent
from shared.contracts.reasoning import ReasoningInput, ReasoningStatus
from shared.detection import detect_transaction
from shared.evidence.agent import EvidenceAgent
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.generator.seed_loader import load_scenario
from shared.persistence.case_document import build_case_document
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client
from shared.policy.evaluator import evaluate_policy
from shared.reasoning.prompt import PROMPT_VERSION
from shared.reasoning.service import ReasoningService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_ui_demo_cases")

DEMO_TRANSACTION_ID = "tx_demo_reasoning_failed"


class AlwaysMalformedReasoningClient:
    """The same scripted-failure double used by tests/reasoning/test_service.py --
    Reasoning's real bounded-retry logic runs for real against this and, exactly
    as designed, exhausts its one reprompt and reports status=FAILED."""

    model_name = "seed-script-forced-failure"

    def generate(self, system_instruction: str, user_content: str) -> types.GenerateContentResponse:
        content = types.Content(role="model", parts=[types.Part.from_text(text="not valid structured output")])
        return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], model_version=self.model_name)


def seed_reasoning_failed_case() -> str:
    """Run the real pipeline building blocks with a forced Reasoning failure and
    write the resulting case for real, for the UI's REASONING_FAILED state.

    :return: The case_id written.
    """
    store = CaseStore(build_firestore_client())

    existing = store.get_case_id_for_transaction(DEMO_TRANSACTION_ID)
    if existing is not None:
        logger.info(f"[seed_reasoning_failed_case] - Already seeded: {existing}")
        return existing

    scenario = load_scenario("branching_proof")
    transaction = scenario.target_transaction.model_copy(update={"transaction_id": DEMO_TRANSACTION_ID})
    case_id = f"case_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    detection: DetectionOutput = detect_transaction(
        transaction=transaction,
        customer=scenario.customer_profile,
        history=list(scenario.baseline_transactions),
        merchant=scenario.merchant_profile,
        secondary_customer=scenario.secondary_profile,
        case_id=case_id,
    )

    document = build_case_document(
        case_id=case_id,
        transaction_id=DEMO_TRANSACTION_ID,
        state=CaseState.DETECTED,
        created_at=now,
        updated_at=now,
        transaction=transaction,
        detection=detection,
    )
    created, resolved_case_id = store.create_case_if_new(DEMO_TRANSACTION_ID, case_id, document)
    if not created:
        return resolved_case_id

    ctx = build_fixture_context(scenario, case_id=case_id)
    agent_input = EvidenceAgentInput(case_id=case_id, transaction=transaction, detection=detection)
    evidence_output = EvidenceAgent(VertexEvidenceAgentClient()).investigate(agent_input, ctx)
    evidence_bundle = evidence_output.evidence_bundle
    evidence_state = (
        CaseState.EVIDENCE_READY if evidence_bundle.completeness == EvidenceCompleteness.COMPLETE else CaseState.EVIDENCE_PARTIAL
    )
    store.update_case(
        case_id, {"state": evidence_state.value, "evidence_bundle": evidence_bundle.model_dump(mode="json")}
    )

    reasoning_input = ReasoningInput(
        case_id=case_id,
        transaction=transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        prompt_version=PROMPT_VERSION,
    )
    reasoning_output = ReasoningService(AlwaysMalformedReasoningClient()).reason(reasoning_input)
    assert reasoning_output.status == ReasoningStatus.FAILED, "seed script expects the forced failure to actually fail"
    store.update_case(case_id, {"state": CaseState.REASONING_FAILED.value})

    policy_decision = evaluate_policy(
        case_id=case_id,
        transaction=transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        reasoning_output=reasoning_output,
    )
    store.update_case(case_id, {"state": CaseState.POLICY_EVALUATED.value, "policy_decision": policy_decision.model_dump(mode="json")})
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=DEMO_TRANSACTION_ID,
            event_type="POLICY_EVALUATED",
            actor_type=ActorType.SYSTEM,
            rule_id=policy_decision.rule_id,
            rule_version=policy_decision.rule_version,
            output_snapshot={"outcome": policy_decision.outcome.value, "reasons": policy_decision.reasons},
            occurred_at=datetime.now(timezone.utc),
        ),
    )
    store.update_case(case_id, {"state": CaseState.HUMAN_REVIEW.value, "updated_at": datetime.now(timezone.utc)})
    store.append_audit_event(
        case_id,
        AuditEvent(
            audit_event_id=f"aud_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            transaction_id=DEMO_TRANSACTION_ID,
            event_type="HUMAN_REVIEW",
            actor_type=ActorType.SYSTEM,
            occurred_at=datetime.now(timezone.utc),
        ),
    )
    logger.info(f"[seed_reasoning_failed_case] - Seeded {case_id}: policy rule_id={policy_decision.rule_id} outcome={policy_decision.outcome.value}")
    return case_id


if __name__ == "__main__":
    seed_reasoning_failed_case()
