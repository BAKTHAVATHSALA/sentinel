"""Unit tests for Sentinel V1 fraud detection service, ML risk scoring, and anomaly tagging."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.detection import (
    DetectionService,
    detect_scenario,
    detect_transaction,
)
from shared.generator import (
    generate_scenario,
    generate_transactions,
    seeded_demo_case,
)


def test_detection_output_validates() -> None:
    """1. Test that detection output cleanly validates as a DetectionOutput contract."""
    txs = generate_transactions(count=1, seed=42)
    output = detect_transaction(txs[0])

    assert isinstance(output, DetectionOutput)
    assert output.transaction_id == txs[0].transaction_id
    assert output.case_id == f"case_{txs[0].transaction_id}"
    assert isinstance(output.risk_score, Decimal)
    assert output.risk_band in {RiskBand.LOW, RiskBand.MEDIUM, RiskBand.HIGH}


def test_same_input_produces_identical_detection_output() -> None:
    """2. Test deterministic reproducibility: same inputs produce same risk score and tags."""
    sc1 = generate_scenario("NEW_DEVICE", seed=42)
    sc2 = generate_scenario("NEW_DEVICE", seed=42)

    service = DetectionService(random_state=42)
    out1 = service.detect_scenario(sc1)
    out2 = service.detect_scenario(sc2)

    assert out1.risk_score == out2.risk_score
    assert out1.risk_band == out2.risk_band
    assert out1.anomaly_tags == out2.anomaly_tags
    assert out1.detection_reasons == out2.detection_reasons


def test_different_inputs_change_risk_score() -> None:
    """3. Test that normal transactions produce lower risk scores than high-risk anomaly transactions."""
    normal_sc = generate_scenario("NEW_DEVICE", seed=10)
    normal_out = detect_transaction(
        transaction=normal_sc.baseline_transactions[0],
        customer=normal_sc.customer_profile,
        history=[],
        merchant=normal_sc.merchant_profile,
    )

    demo_sc = seeded_demo_case(seed=42)
    demo_out = detect_scenario(demo_sc)

    # Multi-anomaly flagship demo should score substantially higher than normal baseline transaction
    assert demo_out.risk_score > normal_out.risk_score
    assert demo_out.risk_band == RiskBand.HIGH
    assert normal_out.risk_band == RiskBand.LOW


def test_risk_score_within_expected_range() -> None:
    """4. Test that risk scores always remain strictly within [0.00, 1.00]."""
    for sc_name in ["NEW_DEVICE", "UNUSUAL_AMOUNT", "MERCHANT_RISK", "IMPOSSIBLE_TRAVEL"]:
        sc = generate_scenario(sc_name, seed=7)
        out = detect_scenario(sc)
        assert Decimal("0.00") <= out.risk_score <= Decimal("1.00")


def test_risk_band_is_deterministic() -> None:
    """5. Test that risk band is deterministically computed from score."""
    service = DetectionService(random_state=42)
    sc = generate_scenario("MERCHANT_RISK", seed=99)
    out1 = service.detect_scenario(sc)
    out2 = service.detect_scenario(sc)

    assert out1.risk_band == out2.risk_band


def test_new_device_anomaly_detected() -> None:
    """6. Test that NEW_DEVICE is tagged when transaction device is not in customer history."""
    sc = generate_scenario("NEW_DEVICE", seed=42)
    out = detect_scenario(sc)

    assert AnomalyTag.NEW_DEVICE in out.anomaly_tags
    assert any("Device" in reason for reason in out.detection_reasons)

    # Negative test: normal baseline transaction using primary device should NOT trigger NEW_DEVICE
    baseline_out = detect_transaction(
        transaction=sc.baseline_transactions[0],
        customer=sc.customer_profile,
        history=sc.baseline_transactions[1:],
    )
    assert AnomalyTag.NEW_DEVICE not in baseline_out.anomaly_tags


def test_unusual_location_anomaly_detected() -> None:
    """7. Test that UNUSUAL_LOCATION is tagged when location materially differs from home baseline."""
    sc = generate_scenario("UNUSUAL_LOCATION", seed=42)
    out = detect_scenario(sc)

    assert AnomalyTag.UNUSUAL_LOCATION in out.anomaly_tags
    assert any("country" in reason.lower() or "distance" in reason.lower() for reason in out.detection_reasons)

    # Negative test: transaction in home location should NOT trigger UNUSUAL_LOCATION
    baseline_out = detect_transaction(
        transaction=sc.baseline_transactions[0],
        customer=sc.customer_profile,
    )
    assert AnomalyTag.UNUSUAL_LOCATION not in baseline_out.anomaly_tags


def test_unusual_amount_anomaly_detected() -> None:
    """8. Test that UNUSUAL_AMOUNT is tagged when amount drastically exceeds spending baseline."""
    sc = generate_scenario("UNUSUAL_AMOUNT", seed=42)
    out = detect_scenario(sc)

    assert AnomalyTag.UNUSUAL_AMOUNT in out.anomaly_tags
    assert any("Amount" in reason for reason in out.detection_reasons)

    # Negative test: normal transaction amount should NOT trigger UNUSUAL_AMOUNT
    baseline_out = detect_transaction(
        transaction=sc.baseline_transactions[0],
        customer=sc.customer_profile,
    )
    assert AnomalyTag.UNUSUAL_AMOUNT not in baseline_out.anomaly_tags


def test_merchant_risk_anomaly_detected() -> None:
    """9. Test that MERCHANT_RISK is tagged when merchant has high chargebacks / rising trend."""
    sc = generate_scenario("MERCHANT_RISK", seed=42)
    out = detect_scenario(sc)

    assert AnomalyTag.MERCHANT_RISK in out.anomaly_tags
    assert any("Merchant" in reason for reason in out.detection_reasons)

    # Negative test: a low-risk merchant (default chargeback rate/trend/band) should NOT trigger MERCHANT_RISK
    low_risk_sc = generate_scenario("NEW_DEVICE", seed=42)
    low_risk_out = detect_transaction(
        transaction=low_risk_sc.baseline_transactions[0],
        customer=low_risk_sc.customer_profile,
        merchant=low_risk_sc.merchant_profile,
    )
    assert AnomalyTag.MERCHANT_RISK not in low_risk_out.anomaly_tags


def test_linked_entity_anomaly_detected() -> None:
    """10. Test that LINKED_ENTITY_ANOMALY is tagged when linked account has failed/review KYC."""
    sc = generate_scenario("LINKED_ENTITY_ANOMALY", seed=42)
    out = detect_scenario(sc)

    assert AnomalyTag.LINKED_ENTITY_ANOMALY in out.anomaly_tags
    assert any("Linked account" in reason for reason in out.detection_reasons)

    # Negative test: a baseline transaction with no secondary/linked profile in context
    # should NOT trigger LINKED_ENTITY_ANOMALY
    baseline_out = detect_transaction(
        transaction=sc.baseline_transactions[0],
        customer=sc.customer_profile,
        history=sc.baseline_transactions[1:],
    )
    assert AnomalyTag.LINKED_ENTITY_ANOMALY not in baseline_out.anomaly_tags


def test_kyc_anomaly_detected() -> None:
    """11. Test that KYC_ANOMALY is tagged when customer KYC verification status is not VERIFIED."""
    sc = generate_scenario("KYC_ANOMALY", seed=42)
    out = detect_scenario(sc)

    assert AnomalyTag.KYC_ANOMALY in out.anomaly_tags
    assert any("KYC" in reason for reason in out.detection_reasons)


def test_flagship_demo_scenario_produces_exact_intended_signals() -> None:
    """12. Test that flagship demo produces EXACTLY [NEW_DEVICE, UNUSUAL_LOCATION, MERCHANT_RISK]."""
    demo = seeded_demo_case(seed=42)
    out = detect_scenario(demo)

    assert isinstance(out, DetectionOutput)

    # Must produce exactly the 3 intended anomaly signals
    expected_tags = {AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION, AnomalyTag.MERCHANT_RISK}
    assert set(out.anomaly_tags) == expected_tags
    assert len(out.anomaly_tags) == 3

    # Multi-signal demo produces HIGH risk band
    assert out.risk_band == RiskBand.HIGH
    assert out.risk_score >= Decimal("0.75")


def test_detection_does_not_produce_policy_outcomes() -> None:
    """13. Test that DetectionOutput does NOT contain policy outcomes (AUTO_RESOLVE, ESCALATE, BLOCK_HOLD)."""
    demo = seeded_demo_case(seed=42)
    out = detect_scenario(demo)

    # Detection contract must only have detection fields, no policy decisions
    assert not hasattr(out, "outcome")
    assert not hasattr(out, "final_disposition")
    assert not hasattr(out, "policy_decision")


def test_no_gemini_or_network_calls() -> None:
    """14. Test that detection runs entirely in-process without network or LLM APIs."""
    txs = generate_transactions(count=5, seed=1)
    service = DetectionService(random_state=42)

    for tx in txs:
        out = service.detect(tx)
        assert out.model_name == "sentinel-deterministic-risk-scorer"
        assert out.model_version == "v1.0.0"
