"""Unit tests for the Phase 3.3 Decision Robustness Scorer (Contracts v1.2
S18): the fast-path materiality estimate (no network dependency) and the
live counterfactual path against a fake, injected ReasoningService double."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.evidence import EvidenceBundle, EvidenceCompleteness
from shared.contracts.fact import Fact, FactQuality
from shared.contracts.reasoning import (
    CaseFindings,
    FindingFactor,
    Materiality,
    ReasoningInput,
    ReasoningOutput,
    ReasoningStatus,
    RecommendedDisposition,
)
from shared.contracts.robustness import RobustnessClassification, RobustnessMethod
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
from shared.robustness.scorer import RobustnessScorer, rebuild_evidence_bundle_without_fact

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)


def _findings(risk_assessment: RiskBand, high_factor_fact_id_groups: list[list[str]]) -> CaseFindings:
    supporting = [
        FindingFactor(statement=f"factor {i}", fact_ids=fact_ids, materiality=Materiality.HIGH)
        for i, fact_ids in enumerate(high_factor_fact_id_groups)
    ]
    return CaseFindings(
        findings_id="find_case_test",
        case_id="case_test",
        risk_assessment=risk_assessment,
        summary="Test findings",
        supporting_factors=supporting,
        counter_factors=[],
        evidence_gaps=[],
        evidence_citations=[],
        recommended_disposition=RecommendedDisposition.ESCALATE,
        generated_at=NOW,
        model_name="test-model",
        model_version="v0",
        prompt_version="reasoning-v1",
    )


def _fact(fact_id: str) -> Fact:
    return Fact(
        fact_id=fact_id,
        type="device_history",
        subject_id="cust_test",
        value={"known_device": False},
        source_tool="get_device_history",
        observed_at=NOW,
        retrieved_at=NOW,
        quality=FactQuality.VERIFIED,
    )


def _bundle(fact_ids: list[str]) -> EvidenceBundle:
    return EvidenceBundle(
        evidence_bundle_id="evb_case_test",
        case_id="case_test",
        facts=[_fact(fid) for fid in fact_ids],
        tools_called=["get_device_history"],
        required_tools=["get_device_history"],
        completeness=EvidenceCompleteness.COMPLETE,
        missing_required_evidence=[],
        conflicts=[],
        started_at=NOW,
        completed_at=NOW,
    )


def _reasoning_input(fact_ids: list[str]) -> ReasoningInput:
    transaction = Transaction(
        transaction_id="tx_test",
        customer_id="cust_test",
        account_id="acc_test",
        card_id="card_test",
        merchant_id="merch_test",
        amount=Decimal("120.00"),
        currency="USD",
        timestamp=NOW,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_test",
        ip_address="198.51.100.1",
        geo=Geo(lat=Decimal("40.7128"), lon=Decimal("-74.0060"), country="USA"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )
    detection = DetectionOutput(
        case_id="case_test",
        transaction_id="tx_test",
        risk_score=Decimal("0.9"),
        risk_band=RiskBand.HIGH,
        anomaly_tags=[AnomalyTag.NEW_DEVICE],
        detection_reasons=["New device"],
        model_name="test-model",
        model_version="v0",
        detected_at=NOW,
    )
    return ReasoningInput(
        case_id="case_test",
        transaction=transaction,
        detection=detection,
        evidence_bundle=_bundle(fact_ids),
        prompt_version="reasoning-v1",
    )


class FakeReasoningService:
    """Scripted fake ReasoningService double -- one queued ReasoningOutput per call."""

    def __init__(self, outputs: list[ReasoningOutput]) -> None:
        self._outputs = list(outputs)
        self.calls: list[ReasoningInput] = []

    def reason(self, reasoning_input: ReasoningInput) -> ReasoningOutput:
        self.calls.append(reasoning_input)
        return self._outputs.pop(0)


def _success_output(risk_assessment: RiskBand) -> ReasoningOutput:
    return ReasoningOutput(
        status=ReasoningStatus.SUCCESS,
        findings=_findings(risk_assessment, []),
        attempts=1,
        failure_reasons=[],
        model_name="fake-gemini-pro",
        model_version="fake-gemini-pro",
    )


def _failed_output() -> ReasoningOutput:
    return ReasoningOutput(
        status=ReasoningStatus.FAILED,
        findings=None,
        attempts=2,
        failure_reasons=["citation invalid twice"],
        model_name="fake-gemini-pro",
        model_version="fake-gemini-pro",
    )


# --- fast_path ---


def test_single_high_materiality_factor_is_fragile_with_fragile_factor_id() -> None:
    findings = _findings(RiskBand.HIGH, [["fact_001"]])
    scorer = RobustnessScorer(FakeReasoningService([]))

    result = scorer.fast_path("case_test", findings)

    assert result.classification == RobustnessClassification.FRAGILE
    assert result.fragile_factor_id == "fact_001"
    assert result.method == RobustnessMethod.FAST_PATH


def test_two_high_materiality_factors_is_robust() -> None:
    findings = _findings(RiskBand.HIGH, [["fact_001"], ["fact_002"]])
    scorer = RobustnessScorer(FakeReasoningService([]))

    result = scorer.fast_path("case_test", findings)

    assert result.classification == RobustnessClassification.ROBUST
    assert result.fragile_factor_id is None


def test_zero_high_materiality_factors_with_high_assessment_is_robust() -> None:
    findings = _findings(RiskBand.HIGH, [])
    scorer = RobustnessScorer(FakeReasoningService([]))

    result = scorer.fast_path("case_test", findings)

    assert result.classification == RobustnessClassification.ROBUST


def test_non_high_risk_assessment_is_robust_trivially() -> None:
    findings = _findings(RiskBand.MEDIUM, [["fact_001"]])
    scorer = RobustnessScorer(FakeReasoningService([]))

    result = scorer.fast_path("case_test", findings)

    assert result.classification == RobustnessClassification.ROBUST


# --- rebuild_evidence_bundle_without_fact ---


def test_rebuild_evidence_bundle_without_fact_excludes_only_that_fact() -> None:
    bundle = _bundle(["fact_001", "fact_002"])

    rebuilt = rebuild_evidence_bundle_without_fact(bundle, "fact_001")

    assert [f.fact_id for f in rebuilt.facts] == ["fact_002"]
    assert rebuilt.evidence_bundle_id != bundle.evidence_bundle_id
    assert [f.fact_id for f in bundle.facts] == ["fact_001", "fact_002"]  # original untouched


# --- live_counterfactual ---


def test_live_counterfactual_classifies_fragile_when_risk_drops_below_threshold() -> None:
    reasoning_input = _reasoning_input(["fact_001", "fact_002"])
    fake_service = FakeReasoningService([_success_output(RiskBand.MEDIUM)])
    scorer = RobustnessScorer(fake_service)

    result = scorer.live_counterfactual("case_test", reasoning_input, "fact_001")

    assert result.classification == RobustnessClassification.FRAGILE
    assert result.fragile_factor_id == "fact_001"
    assert result.method == RobustnessMethod.LIVE_COUNTERFACTUAL
    rebuilt_input = fake_service.calls[0]
    assert "fact_001" not in [f.fact_id for f in rebuilt_input.evidence_bundle.facts]
    assert "fact_002" in [f.fact_id for f in rebuilt_input.evidence_bundle.facts]


def test_live_counterfactual_classifies_robust_when_risk_stays_high() -> None:
    reasoning_input = _reasoning_input(["fact_001", "fact_002"])
    fake_service = FakeReasoningService([_success_output(RiskBand.HIGH)])
    scorer = RobustnessScorer(fake_service)

    result = scorer.live_counterfactual("case_test", reasoning_input, "fact_001")

    assert result.classification == RobustnessClassification.ROBUST
    assert result.fragile_factor_id is None


def test_live_counterfactual_reasoning_failure_is_classified_fragile() -> None:
    reasoning_input = _reasoning_input(["fact_001"])
    fake_service = FakeReasoningService([_failed_output()])
    scorer = RobustnessScorer(fake_service)

    result = scorer.live_counterfactual("case_test", reasoning_input, "fact_001")

    assert result.classification == RobustnessClassification.FRAGILE
    assert result.fragile_factor_id == "fact_001"
