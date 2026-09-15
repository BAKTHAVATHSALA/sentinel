"""Unit tests for the Firestore case document shape (Build Checklist Phase
4.2: "transaction, detection, evidence_bundle, findings, robustness,
policy_decision, state, assigned_analyst_id")."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from shared.contracts.case import CaseState, HumanAction
from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
from shared.persistence.case_document import build_case_document

NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)


def _transaction() -> Transaction:
    return Transaction(
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


def _detection() -> DetectionOutput:
    return DetectionOutput(
        case_id="case_test",
        transaction_id="tx_test",
        risk_score=Decimal("0.10"),
        risk_band=RiskBand.LOW,
        anomaly_tags=[AnomalyTag.NEW_DEVICE],
        detection_reasons=["test"],
        model_name="test-model",
        model_version="v0",
        detected_at=NOW,
    )


def test_minimal_document_has_required_fields_and_null_optional_ones() -> None:
    doc = build_case_document(
        case_id="case_test",
        transaction_id="tx_test",
        state=CaseState.DETECTED,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(),
        detection=_detection(),
    )
    assert doc["case_id"] == "case_test"
    assert doc["transaction_id"] == "tx_test"
    assert doc["state"] == "DETECTED"
    assert doc["transaction"]["amount"] == "120.00"  # Decimal serialized as string, not float
    assert doc["detection"]["risk_band"] == "LOW"
    assert doc["evidence_bundle"] is None
    assert doc["findings"] is None
    assert doc["robustness"] is None
    assert doc["policy_decision"] is None
    assert doc["assigned_analyst_id"] is None
    assert doc["final_disposition"] is None


def test_final_disposition_serializes_as_enum_value() -> None:
    doc = build_case_document(
        case_id="case_test",
        transaction_id="tx_test",
        state=CaseState.FINALIZED,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(),
        detection=_detection(),
        final_disposition=HumanAction.CLEAR,
    )
    assert doc["final_disposition"] == "CLEAR"


def test_document_is_json_safe_no_decimal_or_enum_instances() -> None:
    """Firestore has no native Decimal type -- every value must already be a plain
    str/int/float/bool/None/dict/list."""

    def _assert_json_safe(value: object) -> None:
        if isinstance(value, dict):
            for v in value.values():
                _assert_json_safe(v)
        elif isinstance(value, list):
            for v in value:
                _assert_json_safe(v)
        else:
            assert isinstance(value, (str, int, float, bool, type(None), datetime)), (
                f"Non-JSON-safe value in case document: {value!r} ({type(value)})"
            )

    doc = build_case_document(
        case_id="case_test",
        transaction_id="tx_test",
        state=CaseState.DETECTED,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(),
        detection=_detection(),
    )
    _assert_json_safe(doc)
