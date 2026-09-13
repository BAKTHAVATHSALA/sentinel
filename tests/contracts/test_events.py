"""Unit tests for EventEnvelope, AuditEvent, and ErrorEnvelope contracts."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from shared.contracts.events import ActorType, AuditEvent, ErrorEnvelope, EventEnvelope


def test_event_envelope_generic_payload() -> None:
    """Test EventEnvelope wrapping a typed dictionary payload."""
    payload = {"status": "FLAGGED", "score": 0.9}
    event = EventEnvelope[dict[str, object]](
        event_id="evt_001",
        event_type="CaseFlagged",
        event_version="1.0",
        case_id="case_001",
        transaction_id="tx_001",
        correlation_id="corr_001",
        occurred_at=datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
        producer="detection-service",
        payload=payload,
    )
    assert event.event_id == "evt_001"
    assert event.event_type == "CaseFlagged"
    assert event.payload["status"] == "FLAGGED"


def test_audit_event_actor_types() -> None:
    """Test AuditEvent supports SYSTEM, AGENT, and HUMAN actor types."""
    for actor in [ActorType.SYSTEM, ActorType.AGENT, ActorType.HUMAN]:
        audit = AuditEvent(
            audit_event_id="aud_001",
            case_id="case_001",
            transaction_id="tx_001",
            event_type="PolicyEvaluation",
            actor_type=actor,
            actor_id="agent_evidence_v1",
            occurred_at=datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
            correlation_id="corr_001",
        )
        assert audit.actor_type == actor


def test_error_envelope_creation() -> None:
    """Test ErrorEnvelope creation and optional fields."""
    err = ErrorEnvelope(
        error_code="GEMINI_TIMEOUT",
        message="Gemini model call timed out after 10 seconds",
        retryable=True,
        case_id="case_001",
        transaction_id="tx_001",
        correlation_id="corr_001",
        occurred_at=datetime(2026, 9, 13, 12, 0, 10, tzinfo=timezone.utc),
    )
    assert err.error_code == "GEMINI_TIMEOUT"
    assert err.retryable is True


def test_events_reject_extra_fields() -> None:
    """Test that extra fields on event contracts are rejected."""
    with pytest.raises(ValidationError):
        ErrorEnvelope(
            error_code="ERR",
            message="msg",
            retryable=False,
            correlation_id="c1",
            occurred_at=datetime(2026, 9, 13, tzinfo=timezone.utc),
            extra_debug_info="forbidden",  # type: ignore
        )

    with pytest.raises(ValidationError):
        AuditEvent(
            audit_event_id="a1",
            case_id="c1",
            transaction_id="t1",
            event_type="TYPE",
            actor_type=ActorType.SYSTEM,
            occurred_at=datetime(2026, 9, 13, tzinfo=timezone.utc),
            correlation_id="corr",
            unauthorized_key=123,  # type: ignore
        )
