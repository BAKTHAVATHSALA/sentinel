"""Audit event and error envelope contracts for Sentinel V1.

V1 has no event bus (Contracts V1-Scoped S0/S19): there is no EventEnvelope
here because V1 never carries a payload between services over Pub/Sub --
case_id and transaction_id, threaded through every function call and log
line, are V1's substitute for a distributed correlation ID (S3.1)."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict


class ActorType(str, Enum):
    """Actor triggering or associated with an audit event."""

    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    HUMAN = "HUMAN"


class AuditEvent(BaseModel):
    """Immutable audit trail event recording actions, versions, and states."""

    model_config = ConfigDict(extra="forbid")

    audit_event_id: str
    case_id: str
    transaction_id: str
    event_type: str
    actor_type: ActorType
    actor_id: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    input_snapshot: dict[str, object] | None = None
    output_snapshot: dict[str, object] | None = None
    occurred_at: datetime


class ErrorEnvelope(BaseModel):
    """Structured operational error envelope for failure tracking."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    retryable: bool
    case_id: str | None = None
    transaction_id: str | None = None
    occurred_at: datetime
