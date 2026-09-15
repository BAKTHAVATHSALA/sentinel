"""Schema-only response shape requested from Gemini Pro for one reasoning call.

This is the LLM response contract, not a frozen Sentinel system contract
(Contracts v1.2 S15 only freezes CaseFindings itself). shared.reasoning.service
assembles the full CaseFindings by adding findings_id/case_id/generated_at/
model_name/model_version/prompt_version around this after schema and citation
validation -- keeping Gemini responsible only for the fields it can actually
judge avoids asking it to invent identifiers or timestamps.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from shared.contracts.detection import RiskBand
from shared.contracts.reasoning import FindingFactor, RecommendedDisposition


class GeminiCitation(BaseModel):
    """Citation shape requested from Gemini -- precedent_ids are V1 out of scope (S17)."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    fact_ids: list[str]


class GeminiFindingsPayload(BaseModel):
    """Exact JSON shape requested from Gemini Pro via response_schema: the
    CaseFindings (S15) fields Gemini is actually responsible for producing."""

    model_config = ConfigDict(extra="forbid")

    risk_assessment: RiskBand
    summary: str
    supporting_factors: list[FindingFactor]
    counter_factors: list[FindingFactor]
    evidence_gaps: list[str]
    evidence_citations: list[GeminiCitation]
    recommended_disposition: RecommendedDisposition
