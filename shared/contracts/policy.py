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
    """Request submitted by an analyst executing human decision authority.

    `analyst_id` stays exactly as originally frozen: the backend never trusts
    it -- it verifies the caller's Firebase ID token and rejects any request
    whose `analyst_id` does not match the verified UID (V1 Authoritative
    Ruling Part 1: "if the request body contains analyst_id, verify it
    matches the verified UID; reject mismatch").

    `target_analyst_id` is an additive field (same non-breaking pattern as
    the Addendum 1 Point 4 `counterfactual` response addition -- no existing
    field is removed, renamed, or retyped): required only when
    `action == ESCALATE_SENIOR`, carrying the Firebase UID of the specific
    SENIOR_ANALYST the requesting analyst selected from the UI's senior
    dropdown (V1 Authoritative Ruling Part 4: "analyst selects a Senior
    Analyst from a dropdown ... assigned_analyst_id becomes the selected
    senior's Firebase UID"). The frozen schema had no other slot for this
    value, since `analyst_id` is pinned to the caller's own verified identity
    for every action, including escalation.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    analyst_id: str
    action: HumanAction
    reason: str | None = None
    evidence_acknowledged: bool
    client_timestamp: datetime
    target_analyst_id: str | None = None
