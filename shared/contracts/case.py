"""Case contract and lifecycle state enums for Sentinel V1."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict

from shared.contracts.detection import DetectionOutput


class CaseState(str, Enum):
    """Lifecycle state of an investigation case."""

    RECEIVED = "RECEIVED"
    DETECTED = "DETECTED"
    FLAGGED = "FLAGGED"
    INVESTIGATING = "INVESTIGATING"
    EVIDENCE_READY = "EVIDENCE_READY"
    EVIDENCE_PARTIAL = "EVIDENCE_PARTIAL"
    REASONED = "REASONED"
    REASONING_FAILED = "REASONING_FAILED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    AUTO_RESOLVED = "AUTO_RESOLVED"
    ESCALATED = "ESCALATED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    FINALIZED = "FINALIZED"


class HumanAction(str, Enum):
    """Action that can be executed by a human fraud analyst."""

    CLEAR = "CLEAR"
    BLOCK_HOLD = "BLOCK_HOLD"
    ESCALATE_SENIOR = "ESCALATE_SENIOR"


class Case(BaseModel):
    """Core fraud investigation case entity tracking end-to-end lifecycle."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    transaction_id: str
    state: CaseState
    created_at: datetime
    updated_at: datetime
    detection: DetectionOutput
    evidence_bundle_id: str | None = None
    findings_id: str | None = None
    policy_decision_id: str | None = None
    assigned_analyst_id: str | None = None
    final_disposition: HumanAction | None = None
