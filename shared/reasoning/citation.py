"""Citation validation for Sentinel V1 Reasoning output (Contracts v1.2 S17,
Build Checklist Phase 3.2).

V1 citation validation guarantees structural groundedness only: every
fact_id referenced anywhere in a reasoning payload -- supporting factors,
counter factors, and evidence citations alike -- must exist in the
EvidenceBundle that was actually passed into the call. This is deliberately
independent of the Gemini call itself so it can be unit tested with a
fabricated fact_id and no network dependency.
"""

from __future__ import annotations

from shared.contracts.evidence import EvidenceBundle
from shared.reasoning.schema import GeminiFindingsPayload


def known_fact_ids(evidence_bundle: EvidenceBundle) -> set[str]:
    """Return the set of fact_ids present in the evidence bundle passed to Gemini.

    :param evidence_bundle: The EvidenceBundle given to this reasoning call.
    :return: Set of valid fact_id values.
    """
    return {fact.fact_id for fact in evidence_bundle.facts}


def find_invalid_fact_ids(payload: GeminiFindingsPayload, known_ids: set[str]) -> list[str]:
    """Return every fact_id referenced in the payload that is not in known_ids.

    Checks supporting_factors, counter_factors, and evidence_citations --
    every place Contracts v1.2 S15/S17 lets a claim cite a fact_id.

    :param payload: The schema-validated Gemini response.
    :param known_ids: fact_ids present in the EvidenceBundle passed to Gemini.
    :return: Sorted, de-duplicated list of invalid fact_ids; empty if all valid.
    """
    referenced: set[str] = set()
    for factor in (*payload.supporting_factors, *payload.counter_factors):
        referenced.update(factor.fact_ids)
    for citation in payload.evidence_citations:
        referenced.update(citation.fact_ids)
    return sorted(referenced - known_ids)
