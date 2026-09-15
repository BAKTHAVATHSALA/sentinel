"""Phase 3.1/3.2 real-Gemini integration tests for Reasoning.

These hit Vertex AI for real (Application Default Credentials, no mocked
model responses) -- Contracts v1.2 S15/S17 and the Build Checklist explicitly
require the structured CaseFindings synthesis and citation validation to be
proven against a real Gemini Pro model, not a scripted fake. The
scripted-fake unit tests in test_service.py / test_citation.py cover schema
and citation mechanics in isolation; this file covers the real integration,
chained onto a real Gemini Flash Evidence Agent run so the evidence bundle
Reasoning sees is itself genuine, not fixture-shortcut data.
"""

from __future__ import annotations

from shared.contracts.evidence import EvidenceAgentInput
from shared.contracts.reasoning import ReasoningInput, ReasoningStatus
from shared.detection import detect_scenario
from shared.evidence.agent import EvidenceAgent
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.generator.seed_loader import load_scenario
from shared.reasoning.citation import find_invalid_fact_ids, known_fact_ids
from shared.reasoning.gemini_client import VertexReasoningClient
from shared.reasoning.prompt import PROMPT_VERSION
from shared.reasoning.schema import GeminiCitation, GeminiFindingsPayload
from shared.reasoning.service import ReasoningService


def _gather_evidence(scenario_stem: str, case_id: str):
    scenario = load_scenario(scenario_stem)
    detection = detect_scenario(scenario, case_id=case_id)
    ctx = build_fixture_context(scenario, case_id=case_id)
    agent_input = EvidenceAgentInput(case_id=case_id, transaction=scenario.target_transaction, detection=detection)
    evidence_output = EvidenceAgent(VertexEvidenceAgentClient()).investigate(agent_input, ctx)
    return scenario, detection, evidence_output


def _reason(scenario_stem: str, case_id: str):
    scenario, detection, evidence_output = _gather_evidence(scenario_stem, case_id)
    reasoning_input = ReasoningInput(
        case_id=case_id,
        transaction=scenario.target_transaction,
        detection=detection,
        evidence_bundle=evidence_output.evidence_bundle,
        prompt_version=PROMPT_VERSION,
    )
    output = ReasoningService(VertexReasoningClient()).reason(reasoning_input)
    return output, evidence_output


def test_live_reasoning_on_branching_proof_produces_valid_cited_findings() -> None:
    """Real Gemini Pro reasoning over a real Gemini Flash evidence bundle must succeed
    with schema-valid, fully-grounded CaseFindings."""
    output, evidence_output = _reason("branching_proof", "case_live_reasoning_branch")

    assert output.status == ReasoningStatus.SUCCESS
    assert output.findings is not None

    # Re-validate the full frozen CaseFindings contract shape (Contracts v1.2 S15).
    from shared.contracts.reasoning import CaseFindings

    CaseFindings.model_validate(output.findings.model_dump(mode="json"))

    # Independently re-check groundedness: every cited fact_id must exist in the bundle.
    known_ids = known_fact_ids(evidence_output.evidence_bundle)
    payload = GeminiFindingsPayload(
        risk_assessment=output.findings.risk_assessment,
        summary=output.findings.summary,
        supporting_factors=output.findings.supporting_factors,
        counter_factors=output.findings.counter_factors,
        evidence_gaps=output.findings.evidence_gaps,
        evidence_citations=[
            GeminiCitation(claim_id=c.claim_id, fact_ids=c.fact_ids) for c in output.findings.evidence_citations
        ],
        recommended_disposition=output.findings.recommended_disposition,
    )
    assert find_invalid_fact_ids(payload, known_ids) == []


def test_live_reasoning_on_merchant_risk_trend_produces_valid_cited_findings() -> None:
    """Real Gemini Pro reasoning over the single-signal merchant-risk-trend case must
    also succeed with schema-valid, fully-grounded CaseFindings."""
    output, evidence_output = _reason("merchant_risk_trend", "case_live_reasoning_merchant")

    assert output.status == ReasoningStatus.SUCCESS
    assert output.findings is not None
    assert len(output.findings.supporting_factors) >= 1

    known_ids = known_fact_ids(evidence_output.evidence_bundle)
    cited_fact_ids = {fid for c in output.findings.evidence_citations for fid in c.fact_ids}
    cited_fact_ids |= {fid for f in output.findings.supporting_factors for fid in f.fact_ids}
    cited_fact_ids |= {fid for f in output.findings.counter_factors for fid in f.fact_ids}
    assert cited_fact_ids <= known_ids


def test_live_reasoning_on_partial_evidence_scenario_still_succeeds() -> None:
    """Reasoning must still produce a valid, grounded assessment over a PARTIAL evidence
    bundle -- Policy (Phase 4) is what escalates on completeness=PARTIAL, not Reasoning."""
    from shared.contracts.evidence import EvidenceCompleteness

    output, evidence_output = _reason("partial_evidence", "case_live_reasoning_partial")

    assert evidence_output.evidence_bundle.completeness == EvidenceCompleteness.PARTIAL
    assert output.status == ReasoningStatus.SUCCESS
    assert output.findings is not None
