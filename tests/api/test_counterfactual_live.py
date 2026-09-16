"""Real-Gemini, real-Firestore, real-Firebase-Auth integration test for the
UI counterfactual extension (mega-prompt Section 9/10, Addendum 1 Point 4):
`GET /cases/{case_id}?simulate_without=<fact_id>`.

Builds a real evidence bundle + real Reasoning findings for the
branching_proof seed scenario (the same real-Gemini pattern as
tests/robustness/test_scorer_live.py), seeds a real HUMAN_REVIEW case
document from it, then calls the real endpoint through the real FastAPI app
with a real Firebase ID token -- proving the query parameter reuses the
existing live_counterfactual capability end to end: a second real Gemini
call, a real Policy re-evaluation, and no Firestore write of the result.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from services.api.main import app
from shared.contracts.case import CaseState
from shared.detection import detect_scenario
from shared.evidence.agent import EvidenceAgent
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.contracts.evidence import EvidenceAgentInput
from shared.contracts.reasoning import ReasoningInput, ReasoningStatus
from shared.generator.seed_loader import load_scenario
from shared.persistence.case_document import build_case_document
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client
from shared.policy.evaluator import evaluate_policy
from shared.reasoning.gemini_client import VertexReasoningClient
from shared.reasoning.prompt import PROMPT_VERSION
from shared.reasoning.service import ReasoningService
from shared.robustness.scorer import RobustnessScorer

from tests.api.test_cases_live import ANALYST_1_UID, _auth_headers, _sign_in


def test_live_counterfactual_query_param_end_to_end() -> None:
    suffix = uuid.uuid4().hex[:8]
    case_id, transaction_id = f"case_live_cf_{suffix}", f"tx_live_cf_{suffix}"
    store = CaseStore(build_firestore_client())
    client = TestClient(app)

    scenario = load_scenario("branching_proof")
    detection = detect_scenario(scenario, case_id=case_id)
    ctx = build_fixture_context(scenario, case_id=case_id)
    agent_input = EvidenceAgentInput(case_id=case_id, transaction=scenario.target_transaction, detection=detection)
    evidence_output = EvidenceAgent(VertexEvidenceAgentClient()).investigate(agent_input, ctx)
    evidence_bundle = evidence_output.evidence_bundle
    assert evidence_bundle.facts, "branching_proof must produce at least one fact to remove"

    reasoning_input = ReasoningInput(
        case_id=case_id,
        transaction=scenario.target_transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        prompt_version=PROMPT_VERSION,
    )
    reasoning_service = ReasoningService(VertexReasoningClient())
    reasoning_output = reasoning_service.reason(reasoning_input)
    assert reasoning_output.status == ReasoningStatus.SUCCESS

    original_policy_decision = evaluate_policy(
        case_id=case_id,
        transaction=scenario.target_transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        reasoning_output=reasoning_output,
    )

    document = build_case_document(
        case_id=case_id,
        transaction_id=transaction_id,
        state=CaseState.HUMAN_REVIEW,
        created_at=reasoning_output.findings.generated_at,
        updated_at=reasoning_output.findings.generated_at,
        transaction=scenario.target_transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        findings=reasoning_output.findings,
        policy_decision=original_policy_decision,
        assigned_analyst_id=ANALYST_1_UID,
    )

    try:
        created, _ = store.create_case_if_new(transaction_id, case_id, document)
        assert created is True

        fact_id_to_remove = evidence_bundle.facts[0].fact_id
        token = _sign_in("analyst1@sentinel.demo")

        response = client.get(
            f"/cases/{case_id}", params={"simulate_without": fact_id_to_remove}, headers=_auth_headers(token)
        )

        assert response.status_code == 200
        body = response.json()

        assert "counterfactual" in body
        counterfactual = body["counterfactual"]
        assert counterfactual["removed_fact_id"] == fact_id_to_remove
        assert "robustness" in counterfactual and counterfactual["robustness"]["method"] == "LIVE_COUNTERFACTUAL"
        assert "policy_outcome_would_change" in counterfactual
        assert isinstance(counterfactual["policy_outcome_would_change"], bool)

        # Never persisted: the stored document has no counterfactual field.
        stored = store.get_case(case_id)
        assert "counterfactual" not in stored

        # A normal request (no query param) is unchanged by this feature.
        plain_response = client.get(f"/cases/{case_id}", headers=_auth_headers(token))
        assert "counterfactual" not in plain_response.json()
    finally:
        for doc in store._client.collection(store._cases_collection).document(case_id).collection(
            store._audit_collection
        ).stream():
            doc.reference.delete()
        store._client.collection(store._cases_collection).document(case_id).delete()
        store._client.collection(store._transactions_collection).document(transaction_id).delete()
