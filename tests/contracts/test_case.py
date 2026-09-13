"""Unit tests for Case contract, CaseState, and HumanAction enums."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from shared.contracts.case import Case, CaseState, HumanAction
from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand


def _build_valid_case_payload() -> dict:
    """Build a baseline valid Case payload dictionary."""
    detection = DetectionOutput(
        case_id="case_001",
        transaction_id="tx_001",
        risk_score=Decimal("0.75"),
        risk_band=RiskBand.MEDIUM,
        anomaly_tags=[AnomalyTag.NEW_DEVICE],
        detection_reasons=["New device detected"],
        model_name="detector-v1",
        model_version="1.0.0",
        detected_at=datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
    )
    return {
        "case_id": "case_001",
        "transaction_id": "tx_001",
        "state": CaseState.RECEIVED,
        "created_at": datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
        "detection": detection,
    }


def test_valid_case_creation_with_minimal_fields() -> None:
    """Test Case instantiation with only required fields."""
    payload = _build_valid_case_payload()
    case = Case(**payload)

    assert case.case_id == "case_001"
    assert case.transaction_id == "tx_001"
    assert case.state == CaseState.RECEIVED
    assert isinstance(case.detection, DetectionOutput)
    assert case.evidence_bundle_id is None
    assert case.findings_id is None
    assert case.policy_decision_id is None
    assert case.assigned_analyst_id is None
    assert case.final_disposition is None


def test_valid_case_creation_with_all_optional_fields() -> None:
    """Test Case instantiation with all optional IDs and final disposition."""
    payload = _build_valid_case_payload()
    payload.update(
        {
            "evidence_bundle_id": "eb_001",
            "findings_id": "cf_001",
            "policy_decision_id": "pd_001",
            "assigned_analyst_id": "analyst_42",
            "final_disposition": HumanAction.BLOCK_HOLD,
        }
    )
    case = Case(**payload)

    assert case.evidence_bundle_id == "eb_001"
    assert case.findings_id == "cf_001"
    assert case.policy_decision_id == "pd_001"
    assert case.assigned_analyst_id == "analyst_42"
    assert case.final_disposition == HumanAction.BLOCK_HOLD


@pytest.mark.parametrize(
    "state_name",
    [
        "RECEIVED",
        "DETECTED",
        "FLAGGED",
        "INVESTIGATING",
        "EVIDENCE_READY",
        "EVIDENCE_PARTIAL",
        "REASONED",
        "REASONING_FAILED",
        "POLICY_EVALUATED",
        "AUTO_RESOLVED",
        "ESCALATED",
        "HUMAN_REVIEW",
        "FINALIZED",
    ],
)
def test_all_13_case_states_supported(state_name: str) -> None:
    """Test that all 13 CaseState enum values are valid."""
    payload = _build_valid_case_payload()
    payload["state"] = state_name
    case = Case(**payload)
    assert case.state.value == state_name


@pytest.mark.parametrize("action", ["CLEAR", "BLOCK_HOLD", "ESCALATE_SENIOR"])
def test_all_human_actions_supported(action: str) -> None:
    """Test that all 3 HumanAction enum values are valid."""
    payload = _build_valid_case_payload()
    payload["final_disposition"] = action
    case = Case(**payload)
    assert case.final_disposition is not None
    assert case.final_disposition.value == action


def test_invalid_state_rejected() -> None:
    """Test that unknown case states are rejected."""
    payload = _build_valid_case_payload()
    payload["state"] = "RESOLVED"
    with pytest.raises(ValidationError) as exc_info:
        Case(**payload)
    assert "state" in str(exc_info.value)


def test_invalid_human_action_rejected() -> None:
    """Test that unknown human action is rejected."""
    payload = _build_valid_case_payload()
    payload["final_disposition"] = "AUTO_DECLINE"
    with pytest.raises(ValidationError) as exc_info:
        Case(**payload)
    assert "final_disposition" in str(exc_info.value)


def test_case_rejects_extra_fields() -> None:
    """Test that undeclared fields on Case are rejected."""
    payload = _build_valid_case_payload()
    payload["extra_field"] = "not_allowed"
    with pytest.raises(ValidationError) as exc_info:
        Case(**payload)
    assert "extra_field" in str(exc_info.value)
