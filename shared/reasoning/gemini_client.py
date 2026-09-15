"""Real Vertex AI Gemini Pro client for the Sentinel V1 Reasoning component.

Gemini Pro is configured here deliberately, not Flash: Reasoning makes one
(or, on an invalid-citation/malformed-output reprompt, two) low-volume calls
per case, each synthesizing a full evidence bundle into a structured risk
assessment for a human analyst -- reasoning depth matters far more than
per-call latency or cost here, the inverse tradeoff from the Evidence
Agent's bounded tool-selection loop (shared/evidence/gemini_client.py,
Gemini Flash).

Authentication is Application Default Credentials only -- no API key is
read or stored here.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from shared.config import get_gcp_project_id, get_gcp_region, get_gemini_reasoning_model
from shared.reasoning.schema import GeminiFindingsPayload

# Low but non-zero temperature: reasoning output should be substantively
# consistent for the same evidence bundle across a citation reprompt or a
# live counterfactual re-call, while still reflecting genuine model judgment.
REASONING_TEMPERATURE = 0.1


class VertexReasoningClient:
    """Thin wrapper around the Vertex AI-backed google-genai client, scoped to one
    structured-output Reasoning call."""

    def __init__(self, model_name: str | None = None, temperature: float = REASONING_TEMPERATURE) -> None:
        """Initialize the real Gemini Pro client for Reasoning.

        :param model_name: Override the configured Gemini Pro model name.
        :param temperature: Sampling temperature for the reasoning call.
        """
        self.model_name = model_name or get_gemini_reasoning_model()
        self._temperature = temperature
        self._client = genai.Client(vertexai=True, project=get_gcp_project_id(), location=get_gcp_region())

    def generate(self, system_instruction: str, user_content: str) -> types.GenerateContentResponse:
        """Produce Gemini's structured findings response for one reasoning call.

        :param system_instruction: Reasoning role/rules instruction (no case data).
        :param user_content: The labeled DATA section (transaction, detection, facts).
        :return: The raw Vertex AI GenerateContentResponse.
        """
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=self._temperature,
            response_mime_type="application/json",
            response_schema=GeminiFindingsPayload,
        )
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_content)])]
        return self._client.models.generate_content(model=self.model_name, contents=contents, config=config)
