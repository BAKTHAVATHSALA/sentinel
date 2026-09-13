"""Unit tests for CaseFindings, FindingFactor, Citation, and Precedent contracts."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from shared.contracts.detection import RiskBand
from shared.contracts.reasoning import (
    CaseFindings,
    Citation,
    FindingFactor,
    Materiality,
    Precedent,
    RecommendedDisposition,
)


def _build_valid_case_findings_payload() -> dict:
    """Build a baseline valid CaseFindings payload dictionary."""
    return {
        "findings_id": "findings_001",
        "case_id": "case_001",
        "risk_assessment": RiskBand.HIGH,
        "summary": "Suspicious transaction with new device and rising merchant chargebacks.",
        "supporting_factors": [
            FindingFactor(
                statement="Device first seen 40 minutes prior",
                fact_ids=["fact_01"],
                materiality=Materiality.HIGH,
            )
        ],
        "counter_factors": [
            FindingFactor(
                statement="Customer KYC status verified",
                fact_ids=["fact_02"],
                materiality=Materiality.LOW,
            )
        ],
        "evidence_gaps": [],
        "evidence_citations": [
            Citation(claim_id="claim_01", fact_ids=["fact_01"], precedent_ids=["prec_01"])
        ],
        "recommended_disposition": RecommendedDisposition.ESCALATE,
        "generated_at": datetime(2026, 9, 13, 12, 0, 10, tzinfo=timezone.utc),
        "model_name": "gemini-1.5-pro",
        "model_version": "002",
        "prompt_version": "v1.2",
    }


def test_valid_case_findings_creation() -> None:
    """Test valid CaseFindings creation."""
    payload = _build_valid_case_findings_payload()
    findings = CaseFindings(**payload)

    assert findings.findings_id == "findings_001"
    assert findings.risk_assessment == RiskBand.HIGH
    assert len(findings.supporting_factors) == 1
    assert len(findings.counter_factors) == 1
    assert findings.recommended_disposition == RecommendedDisposition.ESCALATE


def test_case_findings_advisory_recommendations() -> None:
    """Test CaseFindings supports CLEAR, ESCALATE, and BLOCK_HOLD (advisory only)."""
    payload = _build_valid_case_findings_payload()

    payload["recommended_disposition"] = RecommendedDisposition.BLOCK_HOLD
    findings_block = CaseFindings(**payload)
    assert findings_block.recommended_disposition == RecommendedDisposition.BLOCK_HOLD

    payload["recommended_disposition"] = RecommendedDisposition.CLEAR
    findings_clear = CaseFindings(**payload)
    assert findings_clear.recommended_disposition == RecommendedDisposition.CLEAR


def test_finding_factor_materiality() -> None:
    """Test FindingFactor supports HIGH, MEDIUM, LOW materiality."""
    for mat in [Materiality.HIGH, Materiality.MEDIUM, Materiality.LOW]:
        factor = FindingFactor(statement="test", fact_ids=["f1"], materiality=mat)
        assert factor.materiality == mat


def test_citation_precedent_ids_optional() -> None:
    """Test Citation precedent_ids is optional."""
    cit = Citation(claim_id="c1", fact_ids=["f1"])
    assert cit.precedent_ids is None

    cit_with_prec = Citation(claim_id="c1", fact_ids=["f1"], precedent_ids=["p1"])
    assert cit_with_prec.precedent_ids == ["p1"]


def test_precedent_contract() -> None:
    """Test Precedent contract creation and fields."""
    prec = Precedent(
        precedent_id="prec_001",
        case_summary="Similar new device CNP fraud",
        anomaly_tags=["NEW_DEVICE"],
        outcome="BLOCK_HOLD",
        evidence_summary="Device linked to multiple compromised cards",
        source_type="HISTORICAL_CASE",
        created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert prec.precedent_id == "prec_001"
    assert prec.anomaly_tags == ["NEW_DEVICE"]


def test_case_findings_rejects_extra_fields() -> None:
    """Test that extra fields on CaseFindings are rejected."""
    payload = _build_valid_case_findings_payload()
    payload["extra_field"] = "bad"
    with pytest.raises(ValidationError) as exc_info:
        CaseFindings(**payload)
    assert "extra_field" in str(exc_info.value)
