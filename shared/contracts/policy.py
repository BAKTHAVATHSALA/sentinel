"""Deterministic policy rule, decision, and human decision contracts for Sentinel V1."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict

from shared.contracts.case import HumanAction


class PolicyOutcome(str, Enum):
    """Automated outcome produced by deterministic policy evaluation.

    MUST NOT contain BLOCK_HOLD or AUTO_DECLINE under any circumstance.
    """

    AUTO_RESOLVE = "AUTO_RESOLVE"
    ESCALATE = "ESCALATE"


class PolicyRule(BaseModel):
    """Deterministic governance rule evaluated against case evidence and findings."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    version: str
    priority: int
    condition: str
    outcome: PolicyOutcome
    effective_from: datetime
    enabled: bool


class PolicyDecision(BaseModel):
    """Deterministic disposition evaluated by the Policy Decision Service."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    case_id: str
    outcome: PolicyOutcome
    rule_id: str
    rule_version: str
    reasons: list[str]
    inputs_snapshot: dict[str, object]
    evaluated_at: datetime


class HumanDecisionRequest(BaseModel):
    """Request submitted by an analyst executing human decision authority."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    analyst_id: str
    action: HumanAction
    reason: str | None = None
    evidence_acknowledged: bool
    client_timestamp: datetime
