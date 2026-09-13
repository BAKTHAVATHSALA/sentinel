"""Event envelope, audit event, and error envelope contracts for Sentinel V1."""

from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ActorType(str, Enum):
    """Actor triggering or associated with an audit event."""

    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    HUMAN = "HUMAN"


class EventEnvelope(BaseModel, Generic[T]):
    """Standardized event envelope wrapping asynchronous event payloads."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    event_version: str
    case_id: str | None = None
    transaction_id: str | None = None
    correlation_id: str
    occurred_at: datetime
    producer: str
    payload: T


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
    correlation_id: str


class ErrorEnvelope(BaseModel):
    """Structured operational error envelope for failure tracking."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    retryable: bool
    case_id: str | None = None
    transaction_id: str | None = None
    correlation_id: str
    occurred_at: datetime
