"""Unit tests for the Phase 3.1/3.2 bounded ReasoningService loop, using a
scripted fake Gemini client so schema validation, citation-reprompt, and
forced-failure mechanics are tested deterministically and without a network
dependency. Phase 3.1/3.2's real-Gemini requirement is covered separately by
tests/reasoning/test_reasoning_live.py."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest
from google.genai import types

from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.evidence import EvidenceBundle, EvidenceCompleteness
from shared.contracts.fact import Fact, FactQuality
from shared.contracts.reasoning import ReasoningInput, ReasoningStatus
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
from shared.reasoning.service import MAX_GEMINI_CALL_RETRIES, ReasoningService


class FakeGeminiReasoningClient:
    """Scripted fake implementing ReasoningModelClient -- one queued response per call."""

    model_name = "fake-gemini-pro"

    def __init__(self, responses: list[types.GenerateContentResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def generate(self, system_instruction: str, user_content: str):  # noqa: D102 -- test double
        self.calls += 1
        if not self._responses:
            raise AssertionError("FakeGeminiReasoningClient ran out of scripted responses")
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


def _json_response(payload: dict, model_version: str = "fake-gemini-pro") -> types.GenerateContentResponse:
    content = types.Content(role="model", parts=[types.Part.from_text(text=json.dumps(payload))])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], model_version=model_version)


def _text_response(text: str, model_version: str = "fake-gemini-pro") -> types.GenerateContentResponse:
    content = types.Content(role="model", parts=[types.Part.from_text(text=text)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], model_version=model_version)


def _valid_payload(fact_ids: list[str]) -> dict:
    return {
        "risk_assessment": "HIGH",
        "summary": "New device seen on a different account minutes prior.",
        "supporting_factors": [
            {"statement": "New device linked to another account", "fact_ids": fact_ids, "materiality": "HIGH"}
        ],
        "counter_factors": [],
        "evidence_gaps": [],
        "evidence_citations": [{"claim_id": "claim_1", "fact_ids": fact_ids}],
        "recommended_disposition": "ESCALATE",
    }


def _transaction() -> Transaction:
    return Transaction(
        transaction_id="tx_test",
        customer_id="cust_test",
        account_id="acc_test",
        card_id="card_test",
        merchant_id="merch_test",
        amount=Decimal("120.00"),
        currency="USD",
        timestamp=datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc),
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_test",
        ip_address="198.51.100.1",
        geo=Geo(lat=Decimal("40.7128"), lon=Decimal("-74.0060"), country="USA"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )


def _detection() -> DetectionOutput:
    return DetectionOutput(
        case_id="case_test",
        transaction_id="tx_test",
        risk_score=Decimal("0.9"),
        risk_band=RiskBand.HIGH,
        anomaly_tags=[AnomalyTag.NEW_DEVICE],
        detection_reasons=["New device"],
        model_name="test-model",
        model_version="v0",
        detected_at=datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc),
    )


def _fact(fact_id: str) -> Fact:
    now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    return Fact(
        fact_id=fact_id,
        type="device_history",
        subject_id="cust_test",
        value={"known_device": False},
        source_tool="get_device_history",
        observed_at=now,
        retrieved_at=now,
        quality=FactQuality.VERIFIED,
    )


def _reasoning_input(fact_ids: list[str]) -> ReasoningInput:
    now = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    bundle = EvidenceBundle(
        evidence_bundle_id="evb_case_test",
        case_id="case_test",
        facts=[_fact(fid) for fid in fact_ids],
        tools_called=["get_device_history"],
        required_tools=["get_device_history"],
        completeness=EvidenceCompleteness.COMPLETE,
        missing_required_evidence=[],
        conflicts=[],
        started_at=now,
        completed_at=now,
    )
    return ReasoningInput(
        case_id="case_test",
        transaction=_transaction(),
        detection=_detection(),
        evidence_bundle=bundle,
        prompt_version="reasoning-v1",
    )


def test_valid_first_attempt_returns_success() -> None:
    reasoning_input = _reasoning_input(["fact_001"])
    client = FakeGeminiReasoningClient([_json_response(_valid_payload(["fact_001"]))])

    output = ReasoningService(client).reason(reasoning_input)

    assert output.status == ReasoningStatus.SUCCESS
    assert output.attempts == 1
    assert output.failure_reasons == []
    assert output.findings is not None
    assert output.findings.risk_assessment == RiskBand.HIGH
    assert output.findings.case_id == "case_test"
    assert client.calls == 1


def test_invalid_citation_first_attempt_then_valid_reprompt_returns_success() -> None:
    reasoning_input = _reasoning_input(["fact_001"])
    client = FakeGeminiReasoningClient(
        [
            _json_response(_valid_payload(["fact_fabricated"])),
            _json_response(_valid_payload(["fact_001"])),
        ]
    )

    output = ReasoningService(client).reason(reasoning_input)

    assert output.status == ReasoningStatus.SUCCESS
    assert output.attempts == 2
    assert len(output.failure_reasons) == 1
    assert "fact_fabricated" in output.failure_reasons[0]
    assert output.findings is not None
    assert client.calls == 2


def test_invalid_citation_on_both_attempts_marks_failed() -> None:
    reasoning_input = _reasoning_input(["fact_001"])
    client = FakeGeminiReasoningClient(
        [
            _json_response(_valid_payload(["fact_fabricated_1"])),
            _json_response(_valid_payload(["fact_fabricated_2"])),
        ]
    )

    output = ReasoningService(client).reason(reasoning_input)

    assert output.status == ReasoningStatus.FAILED
    assert output.findings is None
    assert output.attempts == 2
    assert len(output.failure_reasons) == 2
    assert client.calls == 2


def test_malformed_json_response_triggers_reprompt_then_failed() -> None:
    reasoning_input = _reasoning_input(["fact_001"])
    client = FakeGeminiReasoningClient(
        [
            _text_response("not valid json at all"),
            _text_response("still not valid json"),
        ]
    )

    output = ReasoningService(client).reason(reasoning_input)

    assert output.status == ReasoningStatus.FAILED
    assert output.findings is None
    assert output.attempts == 2
    assert all("Malformed" in reason for reason in output.failure_reasons)


def test_malformed_then_valid_reprompt_recovers_to_success() -> None:
    reasoning_input = _reasoning_input(["fact_001"])
    client = FakeGeminiReasoningClient(
        [
            _text_response("not json"),
            _json_response(_valid_payload(["fact_001"])),
        ]
    )

    output = ReasoningService(client).reason(reasoning_input)

    assert output.status == ReasoningStatus.SUCCESS
    assert output.attempts == 2
    assert output.findings is not None


def test_gemini_call_exception_exhausts_bounded_retries_and_marks_failed() -> None:
    reasoning_input = _reasoning_input(["fact_001"])
    # Every attempt (2 total) exhausts MAX_GEMINI_CALL_RETRIES+1 transport tries.
    responses = [RuntimeError("network down")] * (2 * (MAX_GEMINI_CALL_RETRIES + 1))
    client = FakeGeminiReasoningClient(responses)

    output = ReasoningService(client).reason(reasoning_input)

    assert output.status == ReasoningStatus.FAILED
    assert output.findings is None
    assert output.attempts == 2
    assert all("failed after bounded retries" in reason for reason in output.failure_reasons)
    assert client.calls == 2 * (MAX_GEMINI_CALL_RETRIES + 1)


def test_transient_gemini_failure_then_recovery_within_one_attempt_succeeds() -> None:
    """A single transient network failure within an attempt's own bounded retries
    should not itself count as a failed attempt -- it should recover silently."""
    reasoning_input = _reasoning_input(["fact_001"])
    client = FakeGeminiReasoningClient(
        [
            RuntimeError("transient"),
            _json_response(_valid_payload(["fact_001"])),
        ]
    )

    output = ReasoningService(client).reason(reasoning_input)

    assert output.status == ReasoningStatus.SUCCESS
    assert output.attempts == 1
    assert output.failure_reasons == []
