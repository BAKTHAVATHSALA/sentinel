"""Phase 2.3 real-Gemini integration tests for the Evidence Agent.

These hit Vertex AI for real (Application Default Credentials, no mocked
model responses) -- Contracts v1.2 S11 and the Build Checklist explicitly
require the bounded function-calling loop to be proven against a real
Gemini Flash model, not a scripted fake. The scripted-fake unit tests in
test_agent.py cover loop mechanics (caps, timeouts, allow-list) in isolation;
this file covers the real integration. The repeated 10-run branching-proof
evidence lives separately in scripts/run_branching_proof.py / eval/.
"""

from __future__ import annotations

from shared.contracts.detection import AnomalyTag
from shared.contracts.evidence import EvidenceAgentInput, EvidenceCompleteness
from shared.detection import detect_scenario
from shared.evidence.agent import EvidenceAgent
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.evidence.tool_specs import EVIDENCE_TOOL_NAMES
from shared.generator.seed_loader import load_scenario


def _run(scenario_stem: str, case_id: str):
    scenario = load_scenario(scenario_stem)
    detection = detect_scenario(scenario, case_id=case_id)
    ctx = build_fixture_context(scenario, case_id=case_id)
    agent_input = EvidenceAgentInput(case_id=case_id, transaction=scenario.target_transaction, detection=detection)
    client = VertexEvidenceAgentClient()
    output = EvidenceAgent(client).investigate(agent_input, ctx)
    return output, detection


def test_live_clean_normal_scenario_needs_no_tool_calls() -> None:
    """1. A clean transaction (no anomaly tags) should be resolvable by real Gemini with
    zero or minimal tool calls, and must end COMPLETE (empty floor)."""
    output, detection = _run("clean_normal", "case_live_clean")

    assert detection.anomaly_tags == []
    assert output.evidence_bundle.completeness == EvidenceCompleteness.COMPLETE
    assert output.model_name == VertexEvidenceAgentClient().model_name
    for tool_name in output.evidence_bundle.tools_called:
        assert tool_name in EVIDENCE_TOOL_NAMES


def test_live_branching_proof_scenario_satisfies_the_floor() -> None:
    """2. Real Gemini investigating the branching-proof scenario must at minimum satisfy
    the NEW_DEVICE floor (call get_device_history) and produce a valid, contract-shaped
    output. Whether it also branches to get_linked_entities on this single run is proven
    reliably (10 repeated runs) by the dedicated Phase 2.4 script, not asserted here."""
    output, detection = _run("branching_proof", "case_live_branching")

    assert detection.anomaly_tags == [AnomalyTag.NEW_DEVICE]
    assert "get_device_history" in output.evidence_bundle.tools_called
    assert output.evidence_bundle.completeness == EvidenceCompleteness.COMPLETE
    assert len(output.evidence_bundle.tools_called) <= 6
    assert output.agent_trace.stopped_reason in {
        "SUFFICIENT_EVIDENCE",
        "MAX_CALLS",
        "FLOOR_SATISFIED",
    }

    from shared.contracts.evidence import EvidenceAgentOutput

    EvidenceAgentOutput.model_validate(output.model_dump(mode="json"))
