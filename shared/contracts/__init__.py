"""Contracts package exposing shared domain models and enums for Sentinel V1."""

from shared.contracts.case import Case, CaseState, HumanAction
from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.events import ActorType, AuditEvent, ErrorEnvelope, EventEnvelope
from shared.contracts.evidence import (
    AgentTrace,
    EvidenceAgentInput,
    EvidenceAgentOutput,
    EvidenceBundle,
    EvidenceCompleteness,
)
from shared.contracts.fact import Fact, FactQuality, Quality
from shared.contracts.policy import (
    HumanDecisionRequest,
    PolicyDecision,
    PolicyOutcome,
    PolicyRule,
)
from shared.contracts.reasoning import (
    CaseFindings,
    Citation,
    FindingFactor,
    Materiality,
    Precedent,
    RecommendedDisposition,
)
from shared.contracts.tools import (
    BehavioralBaselineInput,
    BehavioralBaselineOutput,
    DeviceHistoryInput,
    DeviceHistoryOutput,
    FraudReportTrend,
    IpGeovelocityInput,
    IpGeovelocityOutput,
    KycStatus,
    LinkedEntitiesInput,
    LinkedEntitiesOutput,
    MerchantRiskInput,
    MerchantRiskOutput,
    MockKycInput,
    MockKycOutput,
)
from shared.contracts.transaction import (
    AuthorizationStage,
    Channel,
    Direction,
    Geo,
    PaymentRail,
    Transaction,
)

__all__ = [
    # Case
    "Case",
    "CaseState",
    "HumanAction",
    # Detection
    "AnomalyTag",
    "DetectionOutput",
    "RiskBand",
    # Events & Audit
    "ActorType",
    "AuditEvent",
    "ErrorEnvelope",
    "EventEnvelope",
    # Evidence & Agent
    "AgentTrace",
    "EvidenceAgentInput",
    "EvidenceAgentOutput",
    "EvidenceBundle",
    "EvidenceCompleteness",
    # Fact
    "Fact",
    "FactQuality",
    "Quality",
    # Policy & Human
    "HumanDecisionRequest",
    "PolicyDecision",
    "PolicyOutcome",
    "PolicyRule",
    # Reasoning
    "CaseFindings",
    "Citation",
    "FindingFactor",
    "Materiality",
    "Precedent",
    "RecommendedDisposition",
    # Evidence Tools
    "BehavioralBaselineInput",
    "BehavioralBaselineOutput",
    "DeviceHistoryInput",
    "DeviceHistoryOutput",
    "FraudReportTrend",
    "IpGeovelocityInput",
    "IpGeovelocityOutput",
    "KycStatus",
    "LinkedEntitiesInput",
    "LinkedEntitiesOutput",
    "MerchantRiskInput",
    "MerchantRiskOutput",
    "MockKycInput",
    "MockKycOutput",
    # Transaction
    "AuthorizationStage",
    "Channel",
    "Direction",
    "Geo",
    "PaymentRail",
    "Transaction",
]
