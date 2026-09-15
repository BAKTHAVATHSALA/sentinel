"""Phase 3.3: genuine Decision Robustness Scorer evidence for Sentinel V1.

Runs the full real-Gemini pipeline (Detection -> Evidence Agent [Flash] ->
Reasoning [Pro] -> fast-path estimate -> live counterfactual re-call [Pro])
against the branching_proof and merchant_risk_trend seed scenarios, and
saves the results to eval/robustness_scorer_proof.json.

Every reasoning/robustness call below is a live Gemini call -- nothing here
is scripted or mocked. This is what Build Checklist Phase 3.3's exit
criteria ("Test both paths against the branching-proof scenario and the
merchant-risk-trend scenario specifically -- confirm you get a genuine
FRAGILE result on at least one seeded variant, not only ROBUST results
everywhere") requires as evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict

from shared.contracts.evidence import EvidenceAgentInput
from shared.contracts.reasoning import ReasoningInput
from shared.detection import detect_scenario
from shared.evidence.agent import EvidenceAgent
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.generator.seed_loader import load_scenario
from shared.reasoning.gemini_client import VertexReasoningClient
from shared.reasoning.prompt import PROMPT_VERSION
from shared.reasoning.service import ReasoningService
from shared.robustness.scorer import RobustnessScorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_robustness_proof")

DEFAULT_OUTPUT_PATH = Path("eval/robustness_scorer_proof.json")
SCENARIO_STEMS = ["branching_proof", "merchant_risk_trend"]


def run_one_scenario(scenario_stem: str) -> Dict[str, Any]:
    """Run one scenario through the full real-Gemini pipeline plus both robustness paths.

    :param scenario_stem: Seed scenario file stem (data/seed/scenarios/<stem>.json).
    :return: Structured record of detection, reasoning, and both robustness results.
    """
    case_id = f"case_robustness_proof_{scenario_stem}"
    scenario = load_scenario(scenario_stem)
    detection = detect_scenario(scenario, case_id=case_id)
    ctx = build_fixture_context(scenario, case_id=case_id)
    agent_input = EvidenceAgentInput(case_id=case_id, transaction=scenario.target_transaction, detection=detection)

    started = datetime.now(timezone.utc)
    evidence_output = EvidenceAgent(VertexEvidenceAgentClient()).investigate(agent_input, ctx)

    reasoning_input = ReasoningInput(
        case_id=case_id,
        transaction=scenario.target_transaction,
        detection=detection,
        evidence_bundle=evidence_output.evidence_bundle,
        prompt_version=PROMPT_VERSION,
    )
    reasoning_service = ReasoningService(VertexReasoningClient())
    reasoning_output = reasoning_service.reason(reasoning_input)

    record: Dict[str, Any] = {
        "scenario": scenario_stem,
        "case_id": case_id,
        "anomaly_tags": [t.value for t in detection.anomaly_tags],
        "evidence_completeness": evidence_output.evidence_bundle.completeness.value,
        "tools_called": evidence_output.evidence_bundle.tools_called,
        "reasoning_status": reasoning_output.status.value,
    }

    if reasoning_output.status.value != "SUCCESS" or reasoning_output.findings is None:
        record["reasoning_failure_reasons"] = reasoning_output.failure_reasons
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        return record

    findings = reasoning_output.findings
    record["risk_assessment"] = findings.risk_assessment.value
    record["supporting_factors"] = [
        {"statement": f.statement, "fact_ids": f.fact_ids, "materiality": f.materiality.value}
        for f in findings.supporting_factors
    ]

    scorer = RobustnessScorer(reasoning_service)
    fast_result = scorer.fast_path(case_id, findings)
    record["fast_path"] = {
        "classification": fast_result.classification.value,
        "fragile_factor_id": fast_result.fragile_factor_id,
    }

    if fast_result.fragile_factor_id is not None:
        fact_id_to_remove = fast_result.fragile_factor_id
    else:
        high_factors = [f for f in findings.supporting_factors if f.materiality.value == "HIGH"]
        fact_id_to_remove = high_factors[0].fact_ids[0] if high_factors and high_factors[0].fact_ids else None

    if fact_id_to_remove is not None:
        cf_result = scorer.live_counterfactual(case_id, reasoning_input, fact_id_to_remove)
        record["live_counterfactual"] = {
            "fact_id_removed": fact_id_to_remove,
            "classification": cf_result.classification.value,
        }
    else:
        record["live_counterfactual"] = None

    finished = datetime.now(timezone.utc)
    record["started_at"] = started.isoformat()
    record["finished_at"] = finished.isoformat()
    record["duration_seconds"] = (finished - started).total_seconds()
    logger.info(
        f"[run_one_scenario] - {scenario_stem}: fast_path={record['fast_path']['classification']}, "
        f"live_counterfactual={record['live_counterfactual']}"
    )
    return record


def run_robustness_proof(output_path: Path = DEFAULT_OUTPUT_PATH) -> Dict[str, Any]:
    """Run every scenario in SCENARIO_STEMS through the real pipeline and save evidence.

    :param output_path: Where to save the JSON evidence artifact.
    :return: The full results dict that was saved.
    """
    runs = [run_one_scenario(stem) for stem in SCENARIO_STEMS]

    classifications = [
        r["live_counterfactual"]["classification"] for r in runs if r.get("live_counterfactual") is not None
    ]
    fast_path_classifications = [r["fast_path"]["classification"] for r in runs if "fast_path" in r]
    any_fragile = "FRAGILE" in classifications or "FRAGILE" in fast_path_classifications

    results: Dict[str, Any] = {
        "scenarios": SCENARIO_STEMS,
        "runs": runs,
        "summary": {
            "fast_path_classifications": fast_path_classifications,
            "live_counterfactual_classifications": classifications,
            "genuine_fragile_result_observed": any_fragile,
            "headline": (
                "Decision Robustness Scorer produced at least one genuine FRAGILE result "
                f"across seeded variants: {any_fragile}"
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"[run_robustness_proof] - {results['summary']['headline']}")
    logger.info(f"[run_robustness_proof] - Saved robustness-scorer proof to {output_path}")
    return results


if __name__ == "__main__":
    run_robustness_proof()
