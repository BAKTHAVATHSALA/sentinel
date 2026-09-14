"""Real Vertex AI Gemini client for the Sentinel V1 Evidence Agent.

Gemini Flash is configured here deliberately, not Pro: the Evidence Agent
makes up to 6 bounded tool-selection calls per case (Contracts v1.2 S11.3),
so per-call latency and cost dominate over the deeper reasoning Pro would
add. Reasoning (Phase 3, CaseFindings synthesis) is a separate, lower-volume
component that will use Pro.

Authentication is Application Default Credentials only -- no API key is
read or stored here.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from shared.config import get_gcp_project_id, get_gcp_region, get_gemini_agent_model
from shared.evidence.tool_specs import build_evidence_tool

# Low but non-zero temperature: the agent's tool choices should be
# consistent across the 10 repeated branching-proof runs (Phase 2.4) while
# still reflecting genuine model judgment rather than being deterministic by
# construction.
AGENT_TEMPERATURE = 0.2


class VertexEvidenceAgentClient:
    """Thin wrapper around the Vertex AI-backed google-genai client, scoped to the
    Evidence Agent's bounded function-calling loop."""

    def __init__(self, model_name: str | None = None, temperature: float = AGENT_TEMPERATURE) -> None:
        """Initialize the real Gemini Flash client for the Evidence Agent.

        :param model_name: Override the configured Gemini Flash model name.
        :param temperature: Sampling temperature for tool-selection calls.
        """
        self.model_name = model_name or get_gemini_agent_model()
        self._temperature = temperature
        self._client = genai.Client(vertexai=True, project=get_gcp_project_id(), location=get_gcp_region())
        self._tool = build_evidence_tool()

    def generate_step(
        self, contents: list[types.Content], system_instruction: str
    ) -> types.GenerateContentResponse:
        """Produce Gemini's next step (a function call, or a plain-text stop) for this conversation.

        :param contents: Full conversation so far (case brief + prior tool calls/results).
        :param system_instruction: Investigator role/rules instruction.
        :return: The raw Vertex AI GenerateContentResponse.
        """
        config = types.GenerateContentConfig(
            tools=[self._tool],
            system_instruction=system_instruction,
            temperature=self._temperature,
        )
        return self._client.models.generate_content(model=self.model_name, contents=contents, config=config)
