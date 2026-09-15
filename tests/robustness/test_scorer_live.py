"""Phase 3.3 real-Gemini integration tests for the Decision Robustness Scorer.

These chain a real Gemini Flash Evidence Agent run into a real Gemini Pro
Reasoning call into the fast-path estimate and a real live-counterfactual
Reasoning re-call (Contracts v1.2 S18.2) -- the checklist's "live
counterfactual re-call... used in the live demo moment, not the fast-path
estimate" requires this to be proven against real Gemini, not a fake.

The bulk, repeated-scenario proof (both paths run against branching_proof and
merchant_risk_trend, confirming a genuine FRAGILE result occurs on at least
one seeded variant, exactly as Build Checklist Phase 3.3's exit criteria
require) is generated separately by scripts/run_robustness_proof.py and
saved as eval/robustness_scorer_proof.json -- this file is the narrower
pytest-integrated smoke test.
"""

from __future__ import annotations

from shared.contracts.evidence import EvidenceAgentInput
from shared.contracts.reasoning import ReasoningInput, ReasoningStatus
from shared.contracts.robustness import RobustnessClassification, RobustnessMethod
from shared.detection import detect_scenario
from shared.evidence.agent import EvidenceAgent
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.generator.seed_loader import load_scenario
from shared.reasoning.gemini_client import VertexReasoningClient
from shared.reasoning.prompt import PROMPT_VERSION
from shared.reasoning.service import ReasoningService
from shared.robustness.scorer import RobustnessScorer


def _investigate_and_reason(scenario_stem: str, case_id: str):
    scenario = load_scenario(scenario_stem)
    detection = detect_scenario(scenario, case_id=case_id)
    ctx = build_fixture_context(scenario, case_id=case_id)
    agent_input = EvidenceAgentInput(case_id=case_id, transaction=scenario.target_transaction, detection=detection)
    evidence_output = EvidenceAgent(VertexEvidenceAgentClient()).investigate(agent_input, ctx)

    reasoning_input = ReasoningInput(
        case_id=case_id,
        transaction=scenario.target_transaction,
        detection=detection,
        evidence_bundle=evidence_output.evidence_bundle,
        prompt_version=PROMPT_VERSION,
    )
    reasoning_service = ReasoningService(VertexReasoningClient())
    reasoning_output = reasoning_service.reason(reasoning_input)
    return reasoning_input, reasoning_output, reasoning_service


def test_live_fast_path_and_live_counterfactual_on_merchant_risk_trend() -> None:
    """The single-signal merchant-risk-trend case is seeded so its only evidence tool
    call (get_merchant_risk) backs every supporting factor (data/seed/scenarios/
    merchant_risk_trend.json robustness_demo_note) -- the fast-path estimate reliably
    calls this FRAGILE. The live counterfactual re-call is run for real against
    whatever Gemini genuinely concludes with that fact removed: DetectionOutput's own
    risk_score/MERCHANT_RISK anomaly tag still accompany the re-call (only the
    EvidenceBundle fact is stripped, per Contracts v1.2 S18.2's "rebuild the evidence
    bundle without it"), so a real re-call can still land HIGH from that remaining
    context -- this is genuine model judgment, not asserted here as a fixed outcome.
    The checklist's genuine-FRAGILE-on-at-least-one-variant requirement is proven in
    aggregate by scripts/run_robustness_proof.py's saved eval/robustness_scorer_proof.json."""
    case_id = "case_live_robustness_merchant"
    reasoning_input, reasoning_output, reasoning_service = _investigate_and_reason("merchant_risk_trend", case_id)
    assert reasoning_output.status == ReasoningStatus.SUCCESS
    findings = reasoning_output.findings
    assert findings is not None

    scorer = RobustnessScorer(reasoning_service)
    fast_result = scorer.fast_path(case_id, findings)
    assert fast_result.method == RobustnessMethod.FAST_PATH
    assert fast_result.classification == RobustnessClassification.FRAGILE
    assert fast_result.fragile_factor_id is not None

    cf_result = scorer.live_counterfactual(case_id, reasoning_input, fast_result.fragile_factor_id)
    assert cf_result.method == RobustnessMethod.LIVE_COUNTERFACTUAL
    assert cf_result.classification in {RobustnessClassification.FRAGILE, RobustnessClassification.ROBUST}


def test_live_fast_path_and_live_counterfactual_on_branching_proof() -> None:
    """The branching-proof case's investigation reliably surfaces two independently
    sourced signals (new device + a linked account under active KYC review) -- this
    test proves both robustness paths run for real against that richer case, without
    hard-asserting a specific classification (real Gemini judgment may vary run to run)."""
    case_id = "case_live_robustness_branch"
    reasoning_input, reasoning_output, reasoning_service = _investigate_and_reason("branching_proof", case_id)
    assert reasoning_output.status == ReasoningStatus.SUCCESS
    findings = reasoning_output.findings
    assert findings is not None

    scorer = RobustnessScorer(reasoning_service)
    fast_result = scorer.fast_path(case_id, findings)
    assert fast_result.method == RobustnessMethod.FAST_PATH

    high_factor_fact_id = next(
        (fid for f in findings.supporting_factors if f.materiality.value == "HIGH" for fid in f.fact_ids),
        None,
    )
    if high_factor_fact_id is not None:
        cf_result = scorer.live_counterfactual(case_id, reasoning_input, high_factor_fact_id)
        assert cf_result.method == RobustnessMethod.LIVE_COUNTERFACTUAL
