"""Bounded Gemini Pro reasoning call for Sentinel V1 (Contracts v1.2 S15/S17,
Build Checklist Phase 3.1/3.2).

Reasoning.reason() is a single structured-output synthesis step, not a
second tool-selection agent: it receives a ReasoningInput (transaction,
detection, full evidence bundle) and returns a ReasoningOutput wrapping
either a citation-clean CaseFindings (status=SUCCESS) or a forced-failure
signal (status=FAILED) that Policy rule P-002 (Phase 4) escalates on.

Failure handling is intentionally uniform across the two ways a Gemini
response can be unusable -- malformed/non-schema output (Contracts v1.2 S25)
and a citation referencing a fact_id absent from the evidence bundle
(Contracts v1.2 S17) -- both get exactly one schema-only, stricter reprompt;
a second failure of either kind marks reasoning.status = FAILED rather than
retrying indefinitely (Safety Invariant #10: bounded retries fail safe to
escalation, never a silent drop).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Protocol

from google.genai import types
from pydantic import ValidationError

from shared.contracts.reasoning import (
    CaseFindings,
    Citation,
    ReasoningInput,
    ReasoningOutput,
    ReasoningStatus,
)
from shared.reasoning.citation import find_invalid_fact_ids, known_fact_ids
from shared.reasoning.prompt import PROMPT_VERSION, case_data_block, reprompt_instruction, system_instruction
from shared.reasoning.schema import GeminiFindingsPayload

logger = logging.getLogger("sentinel.reasoning.service")

# Contracts v1.2 S17 / Build Checklist 3.2: one reprompt, then forced failure.
MAX_REASONING_ATTEMPTS = 2

# Bounded retries per Gemini network/transport failure before this attempt
# counts as failed (Contracts v1.2 S25 "Gemini unavailable"; Safety Invariant #10).
MAX_GEMINI_CALL_RETRIES = 2


class ReasoningModelClient(Protocol):
    """Minimal interface the service depends on -- lets tests substitute a fake Gemini client."""

    model_name: str

    def generate(self, system_instruction: str, user_content: str) -> types.GenerateContentResponse:
        """Produce Gemini's structured findings response for one reasoning call."""
        ...


def _extract_text(response: types.GenerateContentResponse) -> str | None:
    candidate = response.candidates[0] if response.candidates else None
    parts = candidate.content.parts if candidate and candidate.content else []
    text_parts = [p.text for p in parts if getattr(p, "text", None)]
    if text_parts:
        return "".join(text_parts)
    return getattr(response, "text", None)


class ReasoningService:
    """Runs the bounded, citation-validated Gemini Pro reasoning call."""

    def __init__(
        self,
        client: ReasoningModelClient,
        max_attempts: int = MAX_REASONING_ATTEMPTS,
        max_gemini_call_retries: int = MAX_GEMINI_CALL_RETRIES,
    ) -> None:
        """Initialize with an injected Gemini client so tests can substitute a fake.

        :param client: Model client implementing ReasoningModelClient.
        :param max_attempts: Total structured-output attempts (initial + reprompts).
        :param max_gemini_call_retries: Bounded transport-level retries per attempt.
        """
        self._client = client
        self._max_attempts = max_attempts
        self._max_gemini_call_retries = max_gemini_call_retries

    def reason(self, reasoning_input: ReasoningInput) -> ReasoningOutput:
        """Run one bounded, citation-validated reasoning call and return ReasoningOutput.

        :param reasoning_input: Frozen ReasoningInput (case_id, transaction, detection,
            evidence_bundle).
        :return: ReasoningOutput -- SUCCESS with a validated CaseFindings, or FAILED after
            the bounded reprompt is exhausted.
        """
        base_instruction = system_instruction()
        data_block = case_data_block(reasoning_input)
        known_ids = known_fact_ids(reasoning_input.evidence_bundle)

        active_instruction = base_instruction
        failure_reasons: list[str] = []
        model_version = self._client.model_name

        for attempt in range(1, self._max_attempts + 1):
            response = self._generate_with_retry(active_instruction, data_block)
            if response is None:
                reason_text = "Gemini reasoning call failed after bounded retries."
                logger.info(f"[reason] - attempt {attempt} failed: {reason_text}")
                failure_reasons.append(reason_text)
                active_instruction = reprompt_instruction(base_instruction, reason_text)
                continue
            model_version = getattr(response, "model_version", None) or model_version

            payload, parse_error = self._parse_payload(response)
            if payload is None:
                reason_text = f"Malformed/non-schema Gemini output: {parse_error}"
                logger.info(f"[reason] - attempt {attempt} failed: {reason_text}")
                failure_reasons.append(reason_text)
                active_instruction = reprompt_instruction(base_instruction, reason_text)
                continue

            invalid_fact_ids = find_invalid_fact_ids(payload, known_ids)
            if invalid_fact_ids:
                reason_text = (
                    f"Citation referenced fact_id(s) not present in the evidence bundle: {invalid_fact_ids}"
                )
                logger.info(f"[reason] - attempt {attempt} failed: {reason_text}")
                failure_reasons.append(reason_text)
                active_instruction = reprompt_instruction(base_instruction, reason_text)
                continue

            findings = self._assemble_findings(reasoning_input, payload, self._client.model_name, model_version)
            return ReasoningOutput(
                status=ReasoningStatus.SUCCESS,
                findings=findings,
                attempts=attempt,
                failure_reasons=failure_reasons,
                model_name=self._client.model_name,
                model_version=model_version,
            )

        logger.info(
            f"[reason] - case {reasoning_input.case_id}: reasoning.status=FAILED after "
            f"{self._max_attempts} attempts: {failure_reasons}"
        )
        return ReasoningOutput(
            status=ReasoningStatus.FAILED,
            findings=None,
            attempts=self._max_attempts,
            failure_reasons=failure_reasons,
            model_name=self._client.model_name,
            model_version=model_version,
        )

    def _generate_with_retry(self, instruction: str, data_block: str) -> types.GenerateContentResponse | None:
        """Call the model with bounded transport-level retries; None only after exhausting them."""
        for attempt in range(1, self._max_gemini_call_retries + 2):
            try:
                return self._client.generate(instruction, data_block)
            except Exception as exc:  # noqa: BLE001 -- Gemini/network failure must never crash the caller
                logger.info(f"[_generate_with_retry] - Gemini call attempt {attempt} failed: {exc}")
        return None

    @staticmethod
    def _parse_payload(response: types.GenerateContentResponse) -> tuple[GeminiFindingsPayload | None, str | None]:
        text = _extract_text(response)
        if not text:
            return None, "empty response"
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            return None, f"invalid JSON ({exc})"
        try:
            return GeminiFindingsPayload.model_validate(raw), None
        except ValidationError as exc:
            return None, f"schema validation failed ({exc})"

    @staticmethod
    def _assemble_findings(
        reasoning_input: ReasoningInput,
        payload: GeminiFindingsPayload,
        model_name: str,
        model_version: str,
    ) -> CaseFindings:
        return CaseFindings(
            findings_id=f"find_{reasoning_input.case_id}",
            case_id=reasoning_input.case_id,
            risk_assessment=payload.risk_assessment,
            summary=payload.summary,
            supporting_factors=payload.supporting_factors,
            counter_factors=payload.counter_factors,
            evidence_gaps=payload.evidence_gaps,
            evidence_citations=[
                Citation(claim_id=c.claim_id, fact_ids=c.fact_ids)
                for c in payload.evidence_citations
            ],
            recommended_disposition=payload.recommended_disposition,
            generated_at=datetime.now(timezone.utc),
            model_name=model_name,
            model_version=model_version,
            prompt_version=PROMPT_VERSION,
        )
