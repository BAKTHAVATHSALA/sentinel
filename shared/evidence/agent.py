"""Bounded Gemini function-calling loop for the Sentinel V1 Evidence Agent
(Contracts v1.2 S11, Build Checklist Phase 2.3/2.4).

The agent is genuinely agentic within hard, code-enforced bounds: Gemini
chooses which tool to call next (or declares itself done) by reacting to
facts already gathered, but it can never exceed the tool-call cap or
investigation deadline, call a tool outside the explicit allow-list, or have
its own "I'm done" judgment override the deterministic minimum-evidence floor
(shared.evidence.floor) when deciding evidence_bundle.completeness.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import json
import logging
import time
from typing import Protocol

from google.genai import types

from shared.contracts.evidence import (
    AgentTrace,
    EvidenceAgentInput,
    EvidenceAgentOutput,
    EvidenceBundle,
    EvidenceCompleteness,
)
from shared.contracts.fact import Fact
from shared.evidence.errors import ToolError, ToolValidationError
from shared.evidence.fixtures import FixtureContext
from shared.evidence.floor import is_floor_satisfied, missing_required_tools, required_tools_for_tags
from shared.evidence.tool_specs import EVIDENCE_TOOL_NAMES
from shared.evidence.tools import call_tool

logger = logging.getLogger("sentinel.evidence.agent")

# Contracts v1.2 S11.3.
MAX_TOOL_CALLS = 6

# Total wall-clock budget for one investigation, across every Gemini turn and
# tool call. Generous relative to fixture-tool latency (~instant except the
# deliberately-forced-failure scenario) because Gemini network latency and
# bounded retries both draw from this same budget.
INVESTIGATION_DEADLINE_SECONDS = 60.0

# Bounded retries per failed tool call (Contracts v1.2 S14 point 1) and per
# failed Gemini call (Safety Invariant #10) before failing safe.
MAX_TOOL_RETRIES = 2
MAX_GEMINI_CALL_RETRIES = 2


class StopReason(str, Enum):
    """Implementation-level stop codes; stored into AgentTrace.stopped_reason (a plain str)."""

    SUFFICIENT_EVIDENCE = "SUFFICIENT_EVIDENCE"
    MAX_CALLS = "MAX_CALLS"
    TIMEOUT = "TIMEOUT"
    TOOL_FAILURE = "TOOL_FAILURE"
    FLOOR_SATISFIED = "FLOOR_SATISFIED"


class EvidenceAgentModelClient(Protocol):
    """Minimal interface the loop depends on -- lets tests substitute a fake Gemini client."""

    model_name: str

    def generate_step(
        self, contents: list[types.Content], system_instruction: str
    ) -> types.GenerateContentResponse:
        """Produce Gemini's next step (a function call, or a plain-text stop) for this conversation."""
        ...


def _system_instruction() -> str:
    return (
        "You are Sentinel's Evidence Agent, investigating a card-not-present fraud case "
        "at the pre-authorization stage. Your job is to gather evidence using the tools "
        "provided so a separate reasoning step can produce a risk assessment for a human "
        "analyst -- you never decide or state the fraud outcome yourself.\n\n"
        "Rules:\n"
        "- You choose which tool to call next, and in what order, based on the case and on "
        "facts already returned by previous tool calls.\n"
        "- You have a hard limit of 6 total tool calls for this investigation.\n"
        "- Every tool argument (customer_id, device_id, account_id, merchant_id, "
        "transaction_id) must come from the case brief below or from a previous tool's "
        "result -- never invent an identifier.\n"
        "- If a tool result reveals a relationship, connection, or signal that looks "
        "materially relevant to fraud risk (for example: a device or identifier also "
        "associated with a different customer or account, or a linked account carrying its "
        "own anomaly), use your own judgment to investigate that lead with an appropriate "
        "tool, even if it was not in the case's originally-listed required tools. Only "
        "follow leads that are materially relevant -- do not call tools speculatively.\n"
        "- The case brief lists tools this case's minimum-evidence floor requires. Call each "
        "of them at least once before you consider the investigation complete.\n"
        "- Once you have gathered sufficient evidence, stop calling tools and reply with a "
        "short plain-text sentence explaining why the evidence is sufficient."
    )


def _case_brief(agent_input: EvidenceAgentInput, required_tools: list[str]) -> str:
    transaction_json = json.dumps(agent_input.transaction.model_dump(mode="json"), indent=2)
    detection_json = json.dumps(agent_input.detection.model_dump(mode="json"), indent=2)
    return (
        f"Case: {agent_input.case_id}\n\n"
        "Transaction under investigation:\n"
        f"```json\n{transaction_json}\n```\n\n"
        "Detection output (deterministic anomaly tags + risk model output):\n"
        f"```json\n{detection_json}\n```\n\n"
        f"This case's minimum-evidence floor requires calling: {required_tools or '(none)'}.\n"
        "Begin your investigation."
    )


def _error_response_part(tool_name: str, message: str) -> types.Part:
    return types.Part.from_function_response(name=tool_name, response={"error": message})


def _call_signature(tool_name: str, args: dict[str, object]) -> str:
    return f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"


def _execute_with_retry(
    tool_name: str,
    args: dict[str, object],
    ctx: FixtureContext,
    call_index: int,
    max_retries: int,
) -> tuple[Fact | None, ToolError | None, int]:
    """Call one tool with bounded retries (Contracts v1.2 S14 point 1).

    Validation errors are never retried -- retrying the same malformed
    arguments cannot succeed. Timeout/execution failures get up to
    max_retries additional attempts before being reported as failed.
    """
    last_error: ToolError | None = None
    for attempt in range(1, max_retries + 2):
        try:
            return call_tool(tool_name, args, ctx, call_index), None, attempt
        except ToolValidationError as exc:
            return None, exc, attempt
        except ToolError as exc:
            last_error = exc
            logger.info(f"[_execute_with_retry] - {tool_name} attempt {attempt} failed: {exc.message}")
    return None, last_error, max_retries + 1


class EvidenceAgent:
    """Runs the bounded, floor-enforced Gemini function-calling investigation loop."""

    def __init__(
        self,
        client: EvidenceAgentModelClient,
        max_calls: int = MAX_TOOL_CALLS,
        deadline_seconds: float = INVESTIGATION_DEADLINE_SECONDS,
        max_tool_retries: int = MAX_TOOL_RETRIES,
    ) -> None:
        """Initialize with an injected Gemini client so tests can substitute a fake.

        :param client: Model client implementing EvidenceAgentModelClient.
        :param max_calls: Hard cap on tool calls for one investigation.
        :param deadline_seconds: Total wall-clock budget for one investigation.
        :param max_tool_retries: Bounded retries per failed tool call.
        """
        self._client = client
        self._max_calls = max_calls
        self._deadline_seconds = deadline_seconds
        self._max_tool_retries = max_tool_retries

    def investigate(self, agent_input: EvidenceAgentInput, ctx: FixtureContext) -> EvidenceAgentOutput:
        """Run one bounded investigation and return the validated EvidenceAgentOutput.

        :param agent_input: The frozen EvidenceAgentInput (case_id, transaction, detection).
        :param ctx: Fixture context this V1 investigation reads tool data from.
        :return: EvidenceAgentOutput with the resulting EvidenceBundle and AgentTrace.
        """
        started_at = datetime.now(timezone.utc)
        deadline = time.monotonic() + self._deadline_seconds
        required_tools = required_tools_for_tags(agent_input.detection.anomaly_tags)

        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part.from_text(text=_case_brief(agent_input, required_tools))])
        ]
        system_instruction = _system_instruction()

        facts: list[Fact] = []
        tools_called: list[str] = []
        selection_reasons: list[str] = []
        seen_call_signatures: set[str] = set()
        call_index = 0
        model_version = self._client.model_name
        stop_reason: StopReason | None = None

        while stop_reason is None:
            if time.monotonic() >= deadline:
                stop_reason = StopReason.TIMEOUT
                break
            if call_index >= self._max_calls:
                stop_reason = StopReason.MAX_CALLS
                break

            response = self._generate_step_with_retry(contents, system_instruction)
            if response is None:
                selection_reasons.append("Gemini call failed after bounded retries.")
                stop_reason = StopReason.TOOL_FAILURE
                break
            model_version = getattr(response, "model_version", None) or model_version

            candidate = response.candidates[0] if response.candidates else None
            parts = candidate.content.parts if candidate and candidate.content else []
            function_calls = [p.function_call for p in parts if p.function_call is not None]
            text_parts = [p.text for p in parts if getattr(p, "text", None)]

            if not function_calls:
                if text_parts:
                    selection_reasons.append(" ".join(text_parts))
                stop_reason = StopReason.SUFFICIENT_EVIDENCE
                break

            contents.append(candidate.content)
            response_parts: list[types.Part] = []
            required_tool_unrecoverable = False

            for fc in function_calls:
                if call_index >= self._max_calls:
                    response_parts.append(_error_response_part(fc.name, "Tool-call budget exhausted"))
                    continue

                tool_name = fc.name
                args = dict(fc.args or {})

                if tool_name not in EVIDENCE_TOOL_NAMES:
                    response_parts.append(_error_response_part(tool_name, f"Tool '{tool_name}' is not permitted"))
                    continue

                signature = _call_signature(tool_name, args)
                if signature in seen_call_signatures and is_floor_satisfied(tools_called, required_tools):
                    stop_reason = StopReason.FLOOR_SATISFIED
                    break
                seen_call_signatures.add(signature)

                call_index += 1
                fact, error, attempts = _execute_with_retry(
                    tool_name, args, ctx, call_index, self._max_tool_retries
                )
                if fact is not None:
                    facts.append(fact)
                    tools_called.append(tool_name)
                    selection_reasons.append(f"Called {tool_name} (resolved on attempt {attempts})")
                    response_parts.append(types.Part.from_function_response(name=tool_name, response=fact.value))
                else:
                    selection_reasons.append(f"{tool_name} failed after {attempts} attempt(s): {error}")
                    response_parts.append(_error_response_part(tool_name, str(error)))
                    if tool_name in required_tools:
                        required_tool_unrecoverable = True

            if response_parts:
                contents.append(types.Content(role="user", parts=response_parts))

            if stop_reason is not None:
                break
            if required_tool_unrecoverable:
                stop_reason = StopReason.TOOL_FAILURE
                break

        completed_at = datetime.now(timezone.utc)
        completeness = (
            EvidenceCompleteness.COMPLETE
            if is_floor_satisfied(tools_called, required_tools)
            else EvidenceCompleteness.PARTIAL
        )
        missing = missing_required_tools(tools_called, required_tools)

        bundle = EvidenceBundle(
            evidence_bundle_id=f"evb_{agent_input.case_id}",
            case_id=agent_input.case_id,
            facts=facts,
            tools_called=tools_called,
            required_tools=required_tools,
            completeness=completeness,
            missing_required_evidence=missing,
            conflicts=[],
            started_at=started_at,
            completed_at=completed_at,
        )
        trace = AgentTrace(
            selected_tools=tools_called,
            selection_reasons=selection_reasons,
            stopped_reason=stop_reason.value,
        )
        return EvidenceAgentOutput(
            evidence_bundle=bundle,
            agent_trace=trace,
            model_name=self._client.model_name,
            model_version=model_version,
        )

    def _generate_step_with_retry(
        self, contents: list[types.Content], system_instruction: str
    ) -> types.GenerateContentResponse | None:
        """Call the model with bounded retries; returns None only after exhausting them."""
        for attempt in range(1, MAX_GEMINI_CALL_RETRIES + 2):
            try:
                return self._client.generate_step(contents, system_instruction)
            except Exception as exc:  # noqa: BLE001 -- Gemini/network failure must never crash the loop
                logger.info(f"[_generate_step_with_retry] - Gemini call attempt {attempt} failed: {exc}")
        return None
