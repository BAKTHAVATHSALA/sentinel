"""Unit tests for Phase 3.2 citation validation (Contracts v1.2 S17): every
fact_id referenced in a reasoning payload must exist in the EvidenceBundle
passed in. No network dependency -- pure function over fixture data."""

from __future__ import annotations

from datetime import datetime, timezone

from shared.contracts.detection import RiskBand
from shared.contracts.evidence import EvidenceBundle, EvidenceCompleteness
from shared.contracts.fact import Fact, FactQuality
from shared.contracts.reasoning import FindingFactor, Materiality, RecommendedDisposition
from shared.reasoning.citation import find_invalid_fact_ids, known_fact_ids
from shared.reasoning.schema import GeminiCitation, GeminiFindingsPayload


def _fact(fact_id: str) -> Fact:
    now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    return Fact(
        fact_id=fact_id,
        type="device_history",
        subject_id="cust_001",
        value={"known_device": False},
        source_tool="get_device_history",
        observed_at=now,
        retrieved_at=now,
        quality=FactQuality.VERIFIED,
    )


def _bundle(fact_ids: list[str]) -> EvidenceBundle:
    now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    return EvidenceBundle(
        evidence_bundle_id="evb_case_001",
        case_id="case_001",
        facts=[_fact(fid) for fid in fact_ids],
        tools_called=["get_device_history"],
        required_tools=["get_device_history"],
        completeness=EvidenceCompleteness.COMPLETE,
        missing_required_evidence=[],
        conflicts=[],
        started_at=now,
        completed_at=now,
    )


def _payload(
    supporting_fact_ids: list[str],
    counter_fact_ids: list[str] | None = None,
    citation_fact_ids: list[str] | None = None,
) -> GeminiFindingsPayload:
    return GeminiFindingsPayload(
        risk_assessment=RiskBand.HIGH,
        summary="Test summary",
        supporting_factors=[
            FindingFactor(statement="New device", fact_ids=supporting_fact_ids, materiality=Materiality.HIGH)
        ],
        counter_factors=(
            [FindingFactor(statement="Counter", fact_ids=counter_fact_ids, materiality=Materiality.LOW)]
            if counter_fact_ids
            else []
        ),
        evidence_gaps=[],
        evidence_citations=(
            [GeminiCitation(claim_id="claim_1", fact_ids=citation_fact_ids)] if citation_fact_ids else []
        ),
        recommended_disposition=RecommendedDisposition.ESCALATE,
    )


def test_known_fact_ids_returns_every_fact_id_in_bundle() -> None:
    bundle = _bundle(["fact_001", "fact_002"])
    assert known_fact_ids(bundle) == {"fact_001", "fact_002"}


def test_valid_citations_pass_when_all_fact_ids_known() -> None:
    bundle = _bundle(["fact_001", "fact_002"])
    payload = _payload(
        supporting_fact_ids=["fact_001"],
        counter_fact_ids=["fact_002"],
        citation_fact_ids=["fact_001", "fact_002"],
    )
    assert find_invalid_fact_ids(payload, known_fact_ids(bundle)) == []


def test_fabricated_fact_id_in_supporting_factor_is_rejected() -> None:
    """Core Phase 3.2 exit test: a fabricated fact_id must be rejected."""
    bundle = _bundle(["fact_001"])
    payload = _payload(supporting_fact_ids=["fact_999_does_not_exist"])

    invalid = find_invalid_fact_ids(payload, known_fact_ids(bundle))

    assert invalid == ["fact_999_does_not_exist"]


def test_fabricated_fact_id_in_counter_factor_is_rejected() -> None:
    bundle = _bundle(["fact_001"])
    payload = _payload(supporting_fact_ids=["fact_001"], counter_fact_ids=["fact_fabricated"])

    invalid = find_invalid_fact_ids(payload, known_fact_ids(bundle))

    assert invalid == ["fact_fabricated"]


def test_fabricated_fact_id_in_evidence_citation_is_rejected() -> None:
    bundle = _bundle(["fact_001"])
    payload = _payload(supporting_fact_ids=["fact_001"], citation_fact_ids=["fact_fabricated"])

    invalid = find_invalid_fact_ids(payload, known_fact_ids(bundle))

    assert invalid == ["fact_fabricated"]


def test_multiple_invalid_fact_ids_are_deduplicated_and_sorted() -> None:
    bundle = _bundle(["fact_001"])
    payload = _payload(
        supporting_fact_ids=["fact_b", "fact_a"],
        citation_fact_ids=["fact_a", "fact_c"],
    )

    invalid = find_invalid_fact_ids(payload, known_fact_ids(bundle))

    assert invalid == ["fact_a", "fact_b", "fact_c"]
