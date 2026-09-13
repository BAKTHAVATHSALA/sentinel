"""Unit tests for EvidenceBundle, EvidenceAgentInput, and EvidenceAgentOutput contracts."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.evidence import (
    AgentTrace,
    EvidenceAgentInput,
    EvidenceAgentOutput,
    EvidenceBundle,
    EvidenceCompleteness,
)
from shared.contracts.fact import Fact, FactQuality
from shared.contracts.transaction import (
    AuthorizationStage,
    Channel,
    Direction,
    Geo,
    PaymentRail,
    Transaction,
)


def _build_test_fact() -> Fact:
    """Helper to create a test Fact instance."""
    return Fact(
        fact_id="fact_test_01",
        type="device_history",
        subject_id="dev_01",
        value={"seen_count": 1},
        source_tool="get_device_history",
        observed_at=datetime(2026, 9, 13, 11, 0, 0, tzinfo=timezone.utc),
        retrieved_at=datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
        quality=FactQuality.VERIFIED,
    )


def _build_test_transaction() -> Transaction:
    """Helper to create a test Transaction instance."""
    return Transaction(
        transaction_id="tx_test_01",
        customer_id="cust_01",
        account_id="acc_01",
        card_id="card_01",
        merchant_id="merch_01",
        amount=Decimal("150.00"),
        currency="USD",
        timestamp=datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_01",
        ip_address="198.51.100.1",
        geo=Geo(lat=Decimal("37.77"), lon=Decimal("-122.41"), country="USA"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )


def _build_test_detection() -> DetectionOutput:
    """Helper to create a test DetectionOutput instance."""
    return DetectionOutput(
        case_id="case_test_01",
        transaction_id="tx_test_01",
        risk_score=Decimal("0.80"),
        risk_band=RiskBand.HIGH,
        anomaly_tags=[AnomalyTag.NEW_DEVICE],
        detection_reasons=["New device observed"],
        model_name="detector-v1",
        model_version="1.0.0",
        detected_at=datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
    )


def _build_test_evidence_bundle() -> EvidenceBundle:
    """Helper to create a test EvidenceBundle instance."""
    return EvidenceBundle(
        evidence_bundle_id="eb_001",
        case_id="case_test_01",
        facts=[_build_test_fact()],
        tools_called=["get_device_history"],
        required_tools=["get_device_history"],
        completeness=EvidenceCompleteness.COMPLETE,
        missing_required_evidence=[],
        conflicts=[],
        started_at=datetime(2026, 9, 13, 12, 0, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 9, 13, 12, 0, 5, tzinfo=timezone.utc),
    )


def test_evidence_bundle_creation() -> None:
    """Test valid EvidenceBundle creation using Fact[] list."""
    bundle = _build_test_evidence_bundle()
    assert bundle.evidence_bundle_id == "eb_001"
    assert len(bundle.facts) == 1
    assert bundle.facts[0].fact_id == "fact_test_01"
    assert bundle.completeness == EvidenceCompleteness.COMPLETE


def test_evidence_bundle_completeness_values() -> None:
    """Test that EvidenceCompleteness supports COMPLETE and PARTIAL."""
    bundle = _build_test_evidence_bundle()
    bundle_partial = bundle.model_copy(update={"completeness": EvidenceCompleteness.PARTIAL})
    assert bundle_partial.completeness == EvidenceCompleteness.PARTIAL


def test_evidence_bundle_rejects_extra_fields() -> None:
    """Test that extra fields on EvidenceBundle are rejected."""
    bundle_dict = _build_test_evidence_bundle().model_dump()
    bundle_dict["extra_key"] = "forbidden"
    with pytest.raises(ValidationError) as exc_info:
        EvidenceBundle(**bundle_dict)
    assert "extra_key" in str(exc_info.value)


def test_evidence_agent_input_creation() -> None:
    """Test EvidenceAgentInput uses Transaction and DetectionOutput models."""
    inp = EvidenceAgentInput(
        case_id="case_test_01",
        transaction=_build_test_transaction(),
        detection=_build_test_detection(),
    )
    assert inp.case_id == "case_test_01"
    assert inp.transaction.transaction_id == "tx_test_01"
    assert inp.detection.risk_band == RiskBand.HIGH


def test_evidence_agent_output_creation() -> None:
    """Test EvidenceAgentOutput uses EvidenceBundle and AgentTrace."""
    trace = AgentTrace(
        selected_tools=["get_device_history"],
        selection_reasons=["Investigate NEW_DEVICE anomaly"],
        stopped_reason="MINIMUM_EVIDENCE_FLOOR_SATISFIED",
    )
    out = EvidenceAgentOutput(
        evidence_bundle=_build_test_evidence_bundle(),
        agent_trace=trace,
        model_name="gemini-1.5-flash",
        model_version="002",
    )
    assert out.evidence_bundle.evidence_bundle_id == "eb_001"
    assert out.agent_trace.stopped_reason == "MINIMUM_EVIDENCE_FLOOR_SATISFIED"
    assert out.model_name == "gemini-1.5-flash"


def test_evidence_agent_output_rejects_extra_fields() -> None:
    """Test that extra fields on EvidenceAgentOutput are rejected."""
    trace = AgentTrace(
        selected_tools=[],
        selection_reasons=[],
        stopped_reason="done",
    )
    with pytest.raises(ValidationError) as exc_info:
        EvidenceAgentOutput(
            evidence_bundle=_build_test_evidence_bundle(),
            agent_trace=trace,
            model_name="flash",
            model_version="1",
            extra_field="invalid",  # type: ignore
        )
    assert "extra_field" in str(exc_info.value)
