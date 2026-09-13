"""Unit tests for DetectionOutput contract, RiskBand, and AnomalyTag enums."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand


def _build_valid_detection_payload() -> dict:
    """Build a baseline valid DetectionOutput payload dictionary."""
    return {
        "case_id": "case_det_001",
        "transaction_id": "tx_det_001",
        "risk_score": Decimal("0.85"),
        "risk_band": RiskBand.HIGH,
        "anomaly_tags": [AnomalyTag.NEW_DEVICE, AnomalyTag.MERCHANT_RISK],
        "detection_reasons": ["Unseen device 40m prior", "Merchant chargeback trend rising"],
        "model_name": "sentinel-deterministic-detector",
        "model_version": "v1.1.0",
        "detected_at": datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
    }


def test_valid_detection_output_creation() -> None:
    """Test valid DetectionOutput instantiation and property types."""
    payload = _build_valid_detection_payload()
    det = DetectionOutput(**payload)

    assert det.case_id == "case_det_001"
    assert det.transaction_id == "tx_det_001"
    assert det.risk_score == Decimal("0.85")
    assert det.risk_band == RiskBand.HIGH
    assert len(det.anomaly_tags) == 2
    assert AnomalyTag.NEW_DEVICE in det.anomaly_tags
    assert det.model_name == "sentinel-deterministic-detector"


@pytest.mark.parametrize(
    "tag",
    [
        "NEW_DEVICE",
        "UNUSUAL_LOCATION",
        "IMPOSSIBLE_TRAVEL",
        "UNUSUAL_AMOUNT",
        "UNUSUAL_TIME",
        "MERCHANT_RISK",
        "LINKED_ENTITY_ANOMALY",
        "KYC_ANOMALY",
    ],
)
def test_all_anomaly_tags_supported(tag: str) -> None:
    """Test that all 8 required anomaly tags are accepted."""
    payload = _build_valid_detection_payload()
    payload["anomaly_tags"] = [tag]
    det = DetectionOutput(**payload)
    assert det.anomaly_tags[0].value == tag


def test_invalid_anomaly_tag_rejected() -> None:
    """Test that unknown anomaly tags are rejected."""
    payload = _build_valid_detection_payload()
    payload["anomaly_tags"] = ["UNKNOWN_TAG"]
    with pytest.raises(ValidationError) as exc_info:
        DetectionOutput(**payload)
    assert "anomaly_tags" in str(exc_info.value)


def test_invalid_risk_band_rejected() -> None:
    """Test that unknown risk band is rejected."""
    payload = _build_valid_detection_payload()
    payload["risk_band"] = "CRITICAL"
    with pytest.raises(ValidationError) as exc_info:
        DetectionOutput(**payload)
    assert "risk_band" in str(exc_info.value)


@pytest.mark.parametrize(
    "field_to_omit",
    [
        "case_id",
        "transaction_id",
        "risk_score",
        "risk_band",
        "anomaly_tags",
        "detection_reasons",
        "model_name",
        "model_version",
        "detected_at",
    ],
)
def test_detection_required_fields_cannot_be_omitted(field_to_omit: str) -> None:
    """Test that omitting any required field raises a validation error."""
    payload = _build_valid_detection_payload()
    del payload[field_to_omit]
    with pytest.raises(ValidationError) as exc_info:
        DetectionOutput(**payload)
    assert field_to_omit in str(exc_info.value)


def test_detection_extra_fields_rejected() -> None:
    """Test that unexpected fields are rejected on DetectionOutput."""
    payload = _build_valid_detection_payload()
    payload["unexpected_metadata"] = 123
    with pytest.raises(ValidationError) as exc_info:
        DetectionOutput(**payload)
    assert "unexpected_metadata" in str(exc_info.value)
