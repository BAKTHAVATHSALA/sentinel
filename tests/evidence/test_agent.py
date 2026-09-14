"""Unit tests for the Phase 2.3 bounded Evidence Agent loop, using a scripted fake
Gemini client so loop mechanics (allow-list, cap, timeout, floor-gating, retries)
are tested deterministically and without a network dependency. Phase 2.3's real-Gemini
requirement is covered separately by tests/evidence/test_agent_live.py."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from google.genai import types

from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.evidence import EvidenceAgentInput, EvidenceCompleteness
from shared.evidence.agent import (
    INVESTIGATION_DEADLINE_SECONDS,
    EvidenceAgent,
    StopReason,
)
from shared.evidence.fixtures import build_fixture_context
from shared.generator.seed_loader import load_scenario


class FakeGeminiClient:
    """Scripted fake implementing EvidenceAgentModelClient -- one queued response per call."""

    model_name = "fake-gemini-flash"

    def __init__(self, responses: list[types.GenerateContentResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def generate_step(self, contents, system_instruction):  # noqa: D102 -- test double
        self.calls += 1
        if not self._responses:
            raise AssertionError("FakeGeminiClient ran out of scripted responses")
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


def _text_response(text: str, model_version: str = "fake-gemini-flash") -> types.GenerateContentResponse:
    content = types.Content(role="model", parts=[types.Part.from_text(text=text)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], model_version=model_version)


def _function_call_response(
    tool_name: str, args: dict[str, object], model_version: str = "fake-gemini-flash"
) -> types.GenerateContentResponse:
    part = types.Part(function_call=types.FunctionCall(name=tool_name, args=args))
    content = types.Content(role="model", parts=[part])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], model_version=model_version)


def _detection_output(case_id: str, tags: list[AnomalyTag]) -> DetectionOutput:
    return DetectionOutput(
        case_id=case_id,
        transaction_id="tx_test",
        risk_score=Decimal("0.9"),
        risk_band=RiskBand.HIGH,
        anomaly_tags=tags,
        detection_reasons=["test"],
        model_name="test-model",
        model_version="v0",
        detected_at=datetime.now(timezone.utc),
    )


def _agent_input(scenario_stem: str, case_id: str, tags: list[AnomalyTag]) -> EvidenceAgentInput:
    scenario = load_scenario(scenario_stem)
    return EvidenceAgentInput(
        case_id=case_id,
        transaction=scenario.target_transaction,
        detection=_detection_output(case_id, tags),
    )


def test_agent_stops_sufficient_evidence_and_completes_when_floor_is_trivially_empty() -> None:
    """1. Verify a clean case (no anomaly tags) stops on Gemini's own text response, COMPLETE."""
    ctx = build_fixture_context(load_scenario("clean_normal"), case_id="case_clean")
    agent_input = _agent_input("clean_normal", "case_clean", [])
    client = FakeGeminiClient([_text_response("No anomalies present; no evidence needed.")])

    output = EvidenceAgent(client).investigate(agent_input, ctx)

    assert output.agent_trace.stopped_reason == StopReason.SUFFICIENT_EVIDENCE.value
    assert output.evidence_bundle.completeness == EvidenceCompleteness.COMPLETE
    assert output.evidence_bundle.tools_called == []
    assert client.calls == 1


def test_agent_marks_partial_when_gemini_declares_done_before_floor_satisfied() -> None:
    """2. Verify the agent NEVER marks COMPLETE just because Gemini "thinks" it's done --
    completeness is computed independently from is_floor_satisfied(), per Contracts v1.2 S10.1."""
    ctx = build_fixture_context(load_scenario("branching_proof"), case_id="case_premature")
    agent_input = _agent_input("branching_proof", "case_premature", [AnomalyTag.NEW_DEVICE])
    client = FakeGeminiClient([_text_response("I believe this is fine, no further checks needed.")])

    output = EvidenceAgent(client).investigate(agent_input, ctx)

    assert output.agent_trace.stopped_reason == StopReason.SUFFICIENT_EVIDENCE.value
    assert output.evidence_bundle.completeness == EvidenceCompleteness.PARTIAL
    assert output.evidence_bundle.missing_required_evidence == ["get_device_history"]


def test_agent_rejects_tool_outside_allow_list_and_continues() -> None:
    """3. Verify a disallowed tool name is rejected (never executed) and reported back to
    Gemini as an error, without crashing the loop."""
    ctx = build_fixture_context(load_scenario("clean_normal"), case_id="case_bad_tool")
    agent_input = _agent_input("clean_normal", "case_bad_tool", [])
    client = FakeGeminiClient(
        [
            _function_call_response("delete_all_records", {"table": "customers"}),
            _text_response("Understood, stopping."),
        ]
    )

    output = EvidenceAgent(client).investigate(agent_input, ctx)

    assert "delete_all_records" not in output.evidence_bundle.tools_called
    assert output.evidence_bundle.facts == []
    assert output.agent_trace.stopped_reason == StopReason.SUFFICIENT_EVIDENCE.value


def test_agent_enforces_max_call_cap() -> None:
    """4. Verify the loop hard-stops at the configured tool-call cap, never exceeding it.

    Uses two distinct tool calls (not a repeat) so the cap -- not duplicate-call
    detection -- is what ends the loop."""
    ctx = build_fixture_context(load_scenario("clean_normal"), case_id="case_cap")
    agent_input = _agent_input("clean_normal", "case_cap", [])
    responses = [
        _function_call_response("get_mock_kyc_status", {"customer_id": ctx.customer.customer_id}),
        _function_call_response(
            "get_device_history",
            {"customer_id": ctx.customer.customer_id, "device_id": ctx.customer.primary_device_id},
        ),
    ]
    client = FakeGeminiClient(responses)

    output = EvidenceAgent(client, max_calls=2).investigate(agent_input, ctx)

    assert output.agent_trace.stopped_reason == StopReason.MAX_CALLS.value
    assert len(output.evidence_bundle.tools_called) == 2
    assert client.calls == 2


def test_agent_investigation_timeout_fails_safe_without_calling_gemini() -> None:
    """5. Verify a zero/near-zero deadline stops immediately with TIMEOUT and never even
    queries Gemini -- the wall-clock bound is enforced before any call. Uses a case with a
    real floor requirement so PARTIAL is a meaningful assertion, not a trivial empty floor."""
    ctx = build_fixture_context(load_scenario("branching_proof"), case_id="case_timeout")
    agent_input = _agent_input("branching_proof", "case_timeout", [AnomalyTag.NEW_DEVICE])
    client = FakeGeminiClient([])  # would raise AssertionError if ever called

    output = EvidenceAgent(client, deadline_seconds=0.0).investigate(agent_input, ctx)

    assert output.agent_trace.stopped_reason == StopReason.TIMEOUT.value
    assert client.calls == 0
    assert output.evidence_bundle.completeness == EvidenceCompleteness.PARTIAL


def test_agent_fails_safe_to_tool_failure_when_gemini_call_exhausts_retries() -> None:
    """6. Verify a Gemini call that keeps failing fails safe (Safety Invariant #10) instead
    of crashing or hanging -- bounded retries, then a clean TOOL_FAILURE stop."""
    ctx = build_fixture_context(load_scenario("clean_normal"), case_id="case_gemini_down")
    agent_input = _agent_input("clean_normal", "case_gemini_down", [])
    client = FakeGeminiClient([RuntimeError("network down")] * 3)

    output = EvidenceAgent(client).investigate(agent_input, ctx)

    assert output.agent_trace.stopped_reason == StopReason.TOOL_FAILURE.value
    assert output.evidence_bundle.facts == []


def test_agent_fails_safe_to_tool_failure_when_required_tool_exhausts_retries() -> None:
    """7. Verify the partial-evidence scenario's forced-failing required tool produces
    TOOL_FAILURE and PARTIAL evidence, proving the fail-safe escalation path end to end."""
    ctx = build_fixture_context(load_scenario("partial_evidence"), case_id="case_partial")
    agent_input = _agent_input("partial_evidence", "case_partial", [AnomalyTag.NEW_DEVICE])
    client = FakeGeminiClient(
        [
            _function_call_response(
                "get_device_history",
                {"customer_id": ctx.customer.customer_id, "device_id": ctx.transaction.device_id},
            )
        ]
    )

    output = EvidenceAgent(client, max_tool_retries=0).investigate(agent_input, ctx)

    assert output.agent_trace.stopped_reason == StopReason.TOOL_FAILURE.value
    assert output.evidence_bundle.completeness == EvidenceCompleteness.PARTIAL
    assert "get_device_history" in output.evidence_bundle.missing_required_evidence


def test_agent_stops_on_duplicate_call_once_floor_already_satisfied() -> None:
    """8. Verify a redundant repeat of an already-answered required call, once the floor
    is already satisfied, triggers a safe FLOOR_SATISFIED stop instead of looping forever."""
    ctx = build_fixture_context(load_scenario("branching_proof"), case_id="case_dup")
    agent_input = _agent_input("branching_proof", "case_dup", [AnomalyTag.NEW_DEVICE])
    call_args = {"customer_id": ctx.customer.customer_id, "device_id": ctx.transaction.device_id}
    client = FakeGeminiClient(
        [
            _function_call_response("get_device_history", call_args),
            _function_call_response("get_device_history", call_args),
        ]
    )

    output = EvidenceAgent(client).investigate(agent_input, ctx)

    assert output.agent_trace.stopped_reason == StopReason.FLOOR_SATISFIED.value
    assert output.evidence_bundle.tools_called == ["get_device_history"]
    assert output.evidence_bundle.completeness == EvidenceCompleteness.COMPLETE


def test_agent_branches_to_linked_entities_when_scripted_to_follow_the_lead() -> None:
    """9. Verify the full happy-path branching sequence (device history -> linked entities ->
    stop) assembles a COMPLETE, two-fact evidence bundle in the right order."""
    ctx = build_fixture_context(load_scenario("branching_proof"), case_id="case_branch")
    agent_input = _agent_input("branching_proof", "case_branch", [AnomalyTag.NEW_DEVICE])
    client = FakeGeminiClient(
        [
            _function_call_response(
                "get_device_history",
                {"customer_id": ctx.customer.customer_id, "device_id": ctx.transaction.device_id},
            ),
            _function_call_response(
                "get_linked_entities",
                {"customer_id": ctx.customer.customer_id, "account_id": "acc_5741"},
            ),
            _text_response("Found a cross-account device link and an anomaly; evidence sufficient."),
        ]
    )

    output = EvidenceAgent(client).investigate(agent_input, ctx)

    assert output.evidence_bundle.tools_called == ["get_device_history", "get_linked_entities"]
    assert output.evidence_bundle.completeness == EvidenceCompleteness.COMPLETE
    assert len(output.evidence_bundle.facts) == 2
    assert output.agent_trace.stopped_reason == StopReason.SUFFICIENT_EVIDENCE.value


def test_agent_output_validates_against_frozen_contract() -> None:
    """10. Verify the assembled output round-trips through the frozen EvidenceAgentOutput
    contract (extra='forbid' on every nested model)."""
    from shared.contracts.evidence import EvidenceAgentOutput

    ctx = build_fixture_context(load_scenario("clean_normal"), case_id="case_contract")
    agent_input = _agent_input("clean_normal", "case_contract", [])
    client = FakeGeminiClient([_text_response("Nothing to investigate.")])

    output = EvidenceAgent(client).investigate(agent_input, ctx)

    assert isinstance(output, EvidenceAgentOutput)
    EvidenceAgentOutput.model_validate(output.model_dump(mode="json"))


def test_default_investigation_deadline_matches_module_constant() -> None:
    """11. Sanity check the exported deadline constant is a sane, positive bound."""
    assert 0 < INVESTIGATION_DEADLINE_SECONDS <= 300
