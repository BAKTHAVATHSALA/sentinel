"""Unit tests for the deterministic Policy evaluator (Contracts V1-Scoped
S15/S16, Build Checklist Phase 4.1) -- one test per rule plus edge cases at
every threshold boundary, exactly as the checklist requires."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.evidence import EvidenceBundle, EvidenceCompleteness
from shared.contracts.policy import PolicyOutcome
from shared.contracts.reasoning import CaseFindings, RecommendedDisposition, ReasoningOutput, ReasoningStatus
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
from shared.policy.constants import HARD_RISK_TAGS
from shared.policy.evaluator import evaluate_policy
from shared.policy.thresholds import HIGH_VALUE_THRESHOLD

NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)


def _transaction(amount: str = "50.00") -> Transaction:
    return Transaction(
        transaction_id="tx_test",
        customer_id="cust_test",
        account_id="acc_test",
        card_id="card_test",
        merchant_id="merch_test",
        amount=Decimal(amount),
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


def _detection(risk_band: RiskBand, tags: list[AnomalyTag] | None = None) -> DetectionOutput:
    risk_score = {"LOW": Decimal("0.10"), "MEDIUM": Decimal("0.50"), "HIGH": Decimal("0.90")}[risk_band.value]
    return DetectionOutput(
        case_id="case_test",
        transaction_id="tx_test",
        risk_score=risk_score,
        risk_band=risk_band,
        anomaly_tags=tags or [],
        detection_reasons=["test"],
        model_name="test-model",
        model_version="v0",
        detected_at=NOW,
    )


def _evidence_bundle(completeness: EvidenceCompleteness, missing: list[str] | None = None) -> EvidenceBundle:
    return EvidenceBundle(
        evidence_bundle_id="evb_case_test",
        case_id="case_test",
        facts=[],
        tools_called=[],
        required_tools=[],
        completeness=completeness,
        missing_required_evidence=missing or [],
        conflicts=[],
        started_at=NOW,
        completed_at=NOW,
    )


def _findings(risk_assessment: RiskBand) -> CaseFindings:
    return CaseFindings(
        findings_id="find_case_test",
        case_id="case_test",
        risk_assessment=risk_assessment,
        summary="test",
        supporting_factors=[],
        counter_factors=[],
        evidence_gaps=[],
        evidence_citations=[],
        recommended_disposition=RecommendedDisposition.ESCALATE,
        generated_at=NOW,
        model_name="test-model",
        model_version="v0",
        prompt_version="reasoning-v1",
    )


def _reasoning_success(risk_assessment: RiskBand) -> ReasoningOutput:
    return ReasoningOutput(
        status=ReasoningStatus.SUCCESS,
        findings=_findings(risk_assessment),
        attempts=1,
        failure_reasons=[],
        model_name="test-model",
        model_version="v0",
    )


def _reasoning_failed() -> ReasoningOutput:
    return ReasoningOutput(
        status=ReasoningStatus.FAILED,
        findings=None,
        attempts=2,
        failure_reasons=["citation invalid twice"],
        model_name="test-model",
        model_version="v0",
    )


def _evaluate(
    risk_band: RiskBand,
    completeness: EvidenceCompleteness,
    reasoning: ReasoningOutput,
    tags: list[AnomalyTag] | None = None,
    amount: str = "50.00",
):
    return evaluate_policy(
        case_id="case_test",
        transaction=_transaction(amount),
        detection=_detection(risk_band, tags),
        evidence_bundle=_evidence_bundle(completeness, missing=(["get_device_history"] if completeness == EvidenceCompleteness.PARTIAL else None)),
        reasoning_output=reasoning,
    )


# --- P-001: incomplete evidence always escalates, regardless of everything else ---


def test_p001_partial_evidence_escalates_even_with_otherwise_clean_low_risk_case() -> None:
    decision = _evaluate(RiskBand.LOW, EvidenceCompleteness.PARTIAL, _reasoning_success(RiskBand.LOW))
    assert decision.outcome == PolicyOutcome.ESCALATE
    assert decision.rule_id == "P-001"


def test_p001_takes_priority_over_p003_and_p004_conditions() -> None:
    """Even a HIGH-value, HIGH-risk case escalates via P-001 (priority 10), not P-003."""
    decision = _evaluate(
        RiskBand.HIGH, EvidenceCompleteness.PARTIAL, _reasoning_success(RiskBand.MEDIUM), amount="1000.00"
    )
    assert decision.rule_id == "P-001"


# --- P-002: risk-assessment tightening ---


def test_p002_medium_risk_band_plus_high_assessment_escalates() -> None:
    decision = _evaluate(RiskBand.MEDIUM, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.HIGH))
    assert decision.outcome == PolicyOutcome.ESCALATE
    assert decision.rule_id == "P-002"


def test_p002_high_risk_band_plus_high_assessment_escalates() -> None:
    decision = _evaluate(RiskBand.HIGH, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.HIGH))
    assert decision.rule_id == "P-002"


def test_p002_boundary_low_risk_band_with_high_assessment_does_not_match_p002() -> None:
    """risk_score >= MEDIUM excludes LOW band -- falls through to Otherwise, still ESCALATE."""
    decision = _evaluate(RiskBand.LOW, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.HIGH))
    assert decision.outcome == PolicyOutcome.ESCALATE
    assert decision.rule_id == "P-005"


# --- P-003: high-value transactions ---


def test_p003_high_risk_band_plus_amount_at_threshold_escalates() -> None:
    decision = _evaluate(
        RiskBand.HIGH,
        EvidenceCompleteness.COMPLETE,
        _reasoning_success(RiskBand.MEDIUM),
        amount=str(HIGH_VALUE_THRESHOLD),
    )
    assert decision.outcome == PolicyOutcome.ESCALATE
    assert decision.rule_id == "P-003"


def test_p003_boundary_amount_just_below_threshold_does_not_match_p003() -> None:
    below = HIGH_VALUE_THRESHOLD - Decimal("0.01")
    decision = _evaluate(
        RiskBand.HIGH, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.MEDIUM), amount=str(below)
    )
    assert decision.rule_id == "P-005"
    assert decision.outcome == PolicyOutcome.ESCALATE  # still escalates via Otherwise


def test_p003_boundary_amount_one_cent_above_threshold_matches_p003() -> None:
    above = HIGH_VALUE_THRESHOLD + Decimal("0.01")
    decision = _evaluate(
        RiskBand.HIGH, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.MEDIUM), amount=str(above)
    )
    assert decision.rule_id == "P-003"


def test_p003_requires_high_risk_band_not_medium() -> None:
    decision = _evaluate(
        RiskBand.MEDIUM,
        EvidenceCompleteness.COMPLETE,
        _reasoning_success(RiskBand.MEDIUM),
        amount="10000.00",
    )
    assert decision.rule_id == "P-005"


def test_p003_fires_even_when_reasoning_failed() -> None:
    """P-003 has no findings dependency -- a large HIGH-risk-score transaction escalates
    even if Reasoning itself failed."""
    decision = _evaluate(
        RiskBand.HIGH, EvidenceCompleteness.COMPLETE, _reasoning_failed(), amount="10000.00"
    )
    assert decision.rule_id == "P-003"
    assert decision.outcome == PolicyOutcome.ESCALATE


# --- P-004: low-risk eligible cases (the only AUTO_RESOLVE rule) ---


def test_p004_low_risk_complete_no_hard_tags_not_high_assessment_auto_resolves() -> None:
    decision = _evaluate(RiskBand.LOW, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.LOW))
    assert decision.outcome == PolicyOutcome.AUTO_RESOLVE
    assert decision.rule_id == "P-004"


def test_p004_statistical_tags_alone_still_auto_resolve() -> None:
    """NEW_DEVICE/UNUSUAL_LOCATION/UNUSUAL_AMOUNT are not HARD_RISK_TAGS -- already priced
    into risk_score."""
    decision = _evaluate(
        RiskBand.LOW,
        EvidenceCompleteness.COMPLETE,
        _reasoning_success(RiskBand.LOW),
        tags=[AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION, AnomalyTag.UNUSUAL_AMOUNT],
    )
    assert decision.outcome == PolicyOutcome.AUTO_RESOLVE
    assert decision.rule_id == "P-004"


def test_p004_each_hard_risk_tag_individually_blocks_auto_resolve() -> None:
    for tag in HARD_RISK_TAGS:
        decision = _evaluate(
            RiskBand.LOW, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.LOW), tags=[tag]
        )
        assert decision.rule_id == "P-005", f"{tag} should have blocked auto-resolve"
        assert decision.outcome == PolicyOutcome.ESCALATE


def test_p004_high_assessment_blocks_auto_resolve_even_at_low_risk_band() -> None:
    """LOW risk_band + HIGH findings.risk_assessment matches neither P-002 (needs risk_band
    != LOW) nor P-004 (needs risk_assessment != HIGH) -- falls through to Otherwise."""
    decision = _evaluate(RiskBand.LOW, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.HIGH))
    assert decision.rule_id == "P-005"
    assert decision.outcome == PolicyOutcome.ESCALATE


def test_p004_reasoning_failed_cannot_auto_resolve() -> None:
    """Critical safety-invariant test: a FAILED reasoning call must never slip into
    AUTO_RESOLVE via P-004, even when risk_band is LOW, evidence is COMPLETE, and no
    hard tag is present."""
    decision = _evaluate(RiskBand.LOW, EvidenceCompleteness.COMPLETE, _reasoning_failed())
    assert decision.outcome == PolicyOutcome.ESCALATE
    assert decision.rule_id == "P-005"


def test_p004_partial_evidence_blocks_auto_resolve() -> None:
    decision = _evaluate(RiskBand.LOW, EvidenceCompleteness.PARTIAL, _reasoning_success(RiskBand.LOW))
    assert decision.outcome == PolicyOutcome.ESCALATE
    assert decision.rule_id == "P-001"


# --- P-005 (Otherwise) ---


def test_otherwise_medium_risk_medium_assessment_escalates() -> None:
    decision = _evaluate(RiskBand.MEDIUM, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.MEDIUM))
    assert decision.outcome == PolicyOutcome.ESCALATE
    assert decision.rule_id == "P-005"


# --- Traceability (Safety Invariant 7) ---


def test_every_decision_records_rule_id_rule_version_reasons_and_inputs_snapshot() -> None:
    decision = _evaluate(RiskBand.LOW, EvidenceCompleteness.COMPLETE, _reasoning_success(RiskBand.LOW))
    assert decision.rule_id
    assert decision.rule_version
    assert len(decision.reasons) > 0
    assert decision.inputs_snapshot
    assert decision.inputs_snapshot["risk_band"] == "LOW"
    assert decision.case_id == "case_test"
    assert decision.decision_id


def test_reasoning_failed_reason_mentions_status_in_otherwise_decision() -> None:
    decision = _evaluate(RiskBand.LOW, EvidenceCompleteness.COMPLETE, _reasoning_failed())
    assert any("FAILED" in reason for reason in decision.reasons)
    assert decision.inputs_snapshot["reasoning_status"] == "FAILED"
    assert decision.inputs_snapshot["findings_risk_assessment"] is None
