"""Evidence bundle and Evidence Agent contracts for Sentinel V1."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict

from shared.contracts.detection import DetectionOutput
from shared.contracts.fact import Fact
from shared.contracts.transaction import Transaction


class EvidenceCompleteness(str, Enum):
    """Completeness state of the gathered evidence bundle."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"


class EvidenceBundle(BaseModel):
    """Aggregated bundle of evidence facts produced by the Evidence Agent."""

    model_config = ConfigDict(extra="forbid")

    evidence_bundle_id: str
    case_id: str
    facts: list[Fact]
    tools_called: list[str]
    required_tools: list[str]
    completeness: EvidenceCompleteness
    missing_required_evidence: list[str]
    conflicts: list[str]
    started_at: datetime
    completed_at: datetime


class EvidenceAgentInput(BaseModel):
    """Input contract for invoking the Evidence Agent."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    transaction: Transaction
    detection: DetectionOutput


class AgentTrace(BaseModel):
    """Trace details documenting tool selection rationale and termination cause."""

    model_config = ConfigDict(extra="forbid")

    selected_tools: list[str]
    selection_reasons: list[str]
    stopped_reason: str


class EvidenceAgentOutput(BaseModel):
    """Output contract produced by the Evidence Agent."""

    model_config = ConfigDict(extra="forbid")

    evidence_bundle: EvidenceBundle
    agent_trace: AgentTrace
    model_name: str
    model_version: str
