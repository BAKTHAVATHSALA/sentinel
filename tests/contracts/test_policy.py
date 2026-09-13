"""Unit tests for deterministic PolicyRule, PolicyDecision, and HumanDecisionRequest contracts."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from shared.contracts.case import HumanAction
from shared.contracts.policy import (
    HumanDecisionRequest,
    PolicyDecision,
    PolicyOutcome,
    PolicyRule,
)


def test_valid_policy_rule_creation() -> None:
    """Test valid PolicyRule creation with AUTO_RESOLVE and ESCALATE."""
    rule_auto = PolicyRule(
        rule_id="RULE_01",
        version="1.0",
        priority=1,
        condition="risk_score <= LOW AND evidence = COMPLETE",
        outcome=PolicyOutcome.AUTO_RESOLVE,
        effective_from=datetime(2026, 9, 13, 0, 0, 0, tzinfo=timezone.utc),
        enabled=True,
    )
    assert rule_auto.outcome == PolicyOutcome.AUTO_RESOLVE

    rule_esc = rule_auto.model_copy(update={"outcome": PolicyOutcome.ESCALATE})
    assert rule_esc.outcome == PolicyOutcome.ESCALATE


def test_policy_rule_cannot_be_block_hold_or_auto_decline() -> None:
    """SAFETY CHECK: PolicyRule MUST NOT accept BLOCK_HOLD or AUTO_DECLINE."""
    base_payload = {
        "rule_id": "RULE_01",
        "version": "1.0",
        "priority": 1,
        "condition": "true",
        "effective_from": datetime(2026, 9, 13, 0, 0, 0, tzinfo=timezone.utc),
        "enabled": True,
    }

    with pytest.raises(ValidationError) as exc_block:
        PolicyRule(**base_payload, outcome="BLOCK_HOLD")  # type: ignore
    assert "outcome" in str(exc_block.value)

    with pytest.raises(ValidationError) as exc_decline:
        PolicyRule(**base_payload, outcome="AUTO_DECLINE")  # type: ignore
    assert "outcome" in str(exc_decline.value)


def test_valid_policy_decision_creation() -> None:
    """Test valid PolicyDecision creation."""
    decision = PolicyDecision(
        decision_id="dec_001",
        case_id="case_001",
        outcome=PolicyOutcome.ESCALATE,
        rule_id="RULE_ESC_01",
        rule_version="1.0",
        reasons=["Evidence completeness is PARTIAL"],
        inputs_snapshot={"evidence_completeness": "PARTIAL"},
        evaluated_at=datetime(2026, 9, 13, 12, 0, 15, tzinfo=timezone.utc),
    )
    assert decision.decision_id == "dec_001"
    assert decision.outcome == PolicyOutcome.ESCALATE


def test_policy_decision_cannot_be_block_hold_or_auto_decline() -> None:
    """SAFETY CHECK: PolicyDecision MUST NOT accept BLOCK_HOLD or AUTO_DECLINE."""
    base_payload = {
        "decision_id": "dec_001",
        "case_id": "case_001",
        "rule_id": "RULE_01",
        "rule_version": "1.0",
        "reasons": ["Risk threshold met"],
        "inputs_snapshot": {},
        "evaluated_at": datetime(2026, 9, 13, 12, 0, 15, tzinfo=timezone.utc),
    }

    with pytest.raises(ValidationError) as exc_block:
        PolicyDecision(**base_payload, outcome="BLOCK_HOLD")  # type: ignore
    assert "outcome" in str(exc_block.value)

    with pytest.raises(ValidationError) as exc_decline:
        PolicyDecision(**base_payload, outcome="AUTO_DECLINE")  # type: ignore
    assert "outcome" in str(exc_decline.value)


def test_human_decision_request_can_accept_block_hold() -> None:
    """SAFETY CHECK: HumanDecisionRequest CAN accept BLOCK_HOLD (human authority only)."""
    req_block = HumanDecisionRequest(
        case_id="case_001",
        analyst_id="analyst_7",
        action=HumanAction.BLOCK_HOLD,
        reason="Confirmed compromised account credentials",
        evidence_acknowledged=True,
        client_timestamp=datetime(2026, 9, 13, 12, 5, 0, tzinfo=timezone.utc),
    )
    assert req_block.action == HumanAction.BLOCK_HOLD

    req_clear = req_block.model_copy(update={"action": HumanAction.CLEAR})
    assert req_clear.action == HumanAction.CLEAR

    req_escalate = req_block.model_copy(update={"action": HumanAction.ESCALATE_SENIOR})
    assert req_escalate.action == HumanAction.ESCALATE_SENIOR


def test_policy_models_reject_extra_fields() -> None:
    """Test that unexpected fields are rejected on Policy contracts."""
    with pytest.raises(ValidationError):
        PolicyRule(
            rule_id="r1",
            version="1",
            priority=1,
            condition="true",
            outcome=PolicyOutcome.ESCALATE,
            effective_from=datetime(2026, 9, 13, tzinfo=timezone.utc),
            enabled=True,
            extra="not_allowed",  # type: ignore
        )

    with pytest.raises(ValidationError):
        HumanDecisionRequest(
            case_id="c1",
            analyst_id="a1",
            action=HumanAction.CLEAR,
            evidence_acknowledged=True,
            client_timestamp=datetime(2026, 9, 13, tzinfo=timezone.utc),
            unknown_flag=True,  # type: ignore
        )
