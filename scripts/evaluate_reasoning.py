"""Build Checklist Phase 5.5: Reasoning schema-validity rate and
citation-validity rate across the full scenario set.

Re-invokes the real Reasoning service (real Gemini Pro, Contracts V1-Scoped
S12) against the real evidence bundles already gathered by the real
Evidence Agent for the 4 flagged Phase 1.4 scenarios -- these are the exact
bundles persisted in the real Firestore cases/{case_id} documents produced
by scripts/run_pipeline_scenarios.py, not synthetic data. Reusing them
avoids re-spending Gemini Flash calls on evidence-gathering that has
already been proven (Phase 2.4/4.3) and isolates this measurement to what
Phase 5.5 actually asks about: Reasoning's own structured-output and
citation behavior.

Per attempt (not per case): schema-valid means the response parsed as
GeminiFindingsPayload; citation-valid means, additionally, every cited
fact_id existed in the evidence bundle. shared.reasoning.service.reason()
records a failure_reasons entry for every attempt that was not both --
prefixed "Malformed/non-schema" or "Citation referenced fact_id(s)" so the
two can be told apart -- and never adds one for the final successful
attempt, so total attempts and per-attempt outcomes are fully
reconstructable from ReasoningOutput alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict

from shared.contracts.reasoning import ReasoningInput
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client
from shared.reasoning.gemini_client import VertexReasoningClient
from shared.reasoning.prompt import PROMPT_VERSION
from shared.reasoning.service import ReasoningService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate_reasoning")

DEFAULT_OUTPUT_PATH = Path("eval/reasoning_validity.json")

# The 4 flagged Phase 1.4 scenarios' real, already-persisted case documents
# (produced by scripts/run_pipeline_scenarios.py against real Gemini/Firestore).
# clean_normal is excluded -- it never reaches Reasoning (Contracts V1-Scoped
# S19: clean transactions skip investigation entirely).
SOURCE_CASE_IDS = {
    "branching_proof": "case_363a3f9bb31b",
    "merchant_risk_trend": "case_eb6fee140535",
    "partial_evidence": "case_24b32015ac18",
    "signature_fraud": "case_e41fc15a8461",
}


def _classify_attempt_failures(failure_reasons: list[str]) -> list[str]:
    """Classify each recorded failed attempt as SCHEMA_INVALID or CITATION_INVALID."""
    classified = []
    for reason in failure_reasons:
        if reason.startswith("Malformed") or reason.startswith("Gemini reasoning call failed"):
            classified.append("SCHEMA_INVALID")
        elif reason.startswith("Citation referenced"):
            classified.append("CITATION_INVALID")
        else:
            classified.append("UNKNOWN")
    return classified


def evaluate_reasoning_validity(output_path: Path = DEFAULT_OUTPUT_PATH) -> Dict[str, Any]:
    """Re-run real Reasoning against each scenario's real evidence bundle and measure
    schema/citation validity per attempt.

    :param output_path: Where to save the JSON evidence artifact.
    :return: The full results dict that was saved.
    """
    store = CaseStore(build_firestore_client())
    reasoning_service = ReasoningService(VertexReasoningClient())

    runs = []
    total_attempts = 0
    schema_invalid_attempts = 0
    citation_invalid_attempts = 0

    for scenario_stem, case_id in SOURCE_CASE_IDS.items():
        document = store.get_case(case_id)
        if document is None:
            logger.warning(f"[evaluate_reasoning_validity] - {scenario_stem}: case {case_id} not found, skipping")
            continue

        reasoning_input = ReasoningInput.model_validate(
            {
                "case_id": f"eval_{document['case_id']}",
                "transaction": document["transaction"],
                "detection": document["detection"],
                "evidence_bundle": document["evidence_bundle"],
                "prompt_version": PROMPT_VERSION,
            }
        )
        output = reasoning_service.reason(reasoning_input)

        classified_failures = _classify_attempt_failures(output.failure_reasons)
        final_attempt_valid = output.status.value == "SUCCESS"
        attempt_outcomes = classified_failures + (["VALID"] if final_attempt_valid else [])

        total_attempts += len(attempt_outcomes)
        schema_invalid_attempts += sum(1 for o in attempt_outcomes if o == "SCHEMA_INVALID")
        citation_invalid_attempts += sum(1 for o in attempt_outcomes if o == "CITATION_INVALID")

        record = {
            "scenario": scenario_stem,
            "source_case_id": case_id,
            "final_status": output.status.value,
            "attempts_made": output.attempts,
            "attempt_outcomes": attempt_outcomes,
            "failure_reasons": output.failure_reasons,
        }
        logger.info(f"[evaluate_reasoning_validity] - {scenario_stem}: {attempt_outcomes}")
        runs.append(record)

    schema_valid_attempts = total_attempts - schema_invalid_attempts
    citation_eligible_attempts = schema_valid_attempts  # citations can't be checked on a malformed attempt
    citation_valid_attempts = citation_eligible_attempts - citation_invalid_attempts

    results: Dict[str, Any] = {
        "title": "Sentinel V1 Phase 5.5 -- Reasoning schema-validity and citation-validity rates",
        "methodology": (
            "Real Gemini Pro reasoning calls (shared.reasoning.service.ReasoningService, "
            "shared.reasoning.gemini_client.VertexReasoningClient) against the real, "
            "already-persisted evidence bundles for the 4 flagged Phase 1.4 scenarios. "
            "Measured per attempt, not per case, since a case can require a reprompt "
            "(Contracts V1-Scoped S17) -- each attempt independently either parsed as "
            "valid structured output or did not, and if it did, either every cited "
            "fact_id existed in the evidence bundle or it did not."
        ),
        "scenarios_evaluated": list(SOURCE_CASE_IDS.keys()),
        "runs": runs,
        "summary": {
            "total_attempts": total_attempts,
            "schema_valid_attempts": schema_valid_attempts,
            "schema_validity_rate": schema_valid_attempts / total_attempts if total_attempts else None,
            "citation_eligible_attempts": citation_eligible_attempts,
            "citation_valid_attempts": citation_valid_attempts,
            "citation_validity_rate": (
                citation_valid_attempts / citation_eligible_attempts if citation_eligible_attempts else None
            ),
            "cases_reaching_success": sum(1 for r in runs if r["final_status"] == "SUCCESS"),
            "cases_total": len(runs),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(
        f"[evaluate_reasoning_validity] - schema_validity_rate="
        f"{results['summary']['schema_validity_rate']} citation_validity_rate="
        f"{results['summary']['citation_validity_rate']}"
    )
    logger.info(f"[evaluate_reasoning_validity] - Saved to {output_path}")
    return results


if __name__ == "__main__":
    evaluate_reasoning_validity()
