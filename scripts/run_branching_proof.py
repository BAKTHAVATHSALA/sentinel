"""Phase 2.4: genuine repeated-run branching-proof evidence for the Sentinel V1 Evidence Agent.

Runs the committed branching_proof seed scenario through the real Vertex
AI Gemini Flash-backed Evidence Agent N times (default 10), logging the
exact tool-call sequence each run produces, and saves the full log plus a
branching success rate to eval/evidence_agent_branching.json.

Every run below is a live Gemini function-calling call -- nothing here is
scripted or mocked. This is what the Build Checklist Phase 2.4 exit
criteria ("Re-run this exact scenario at least 10 times; confirm the
branching happens reliably, not occasionally") requires as evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict

from shared.contracts.evidence import EvidenceAgentInput
from shared.detection import detect_scenario
from shared.evidence.agent import EvidenceAgent
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.gemini_client import VertexEvidenceAgentClient
from shared.generator.seed_loader import load_scenario

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_branching_proof")

DEFAULT_RUN_COUNT = 10
DEFAULT_OUTPUT_PATH = Path("eval/evidence_agent_branching.json")
SCENARIO_STEM = "branching_proof"
REQUIRED_FIRST_TOOL = "get_device_history"
BRANCH_TOOL = "get_linked_entities"

FIXED_MAPPING_FAILURE_PATTERN_NOTE = (
    "A fake/fixed-mapping agent would hard-code a rule like 'if the NEW_DEVICE tag is "
    "present, always call get_device_history then get_linked_entities' -- it would branch "
    "10/10 times for a reason that has nothing to do with what get_device_history actually "
    "returned, and it would branch identically even if the device_history fixture were "
    "changed to show no cross-account signal at all. This implementation never encodes "
    "get_linked_entities as a required or expected follow-up anywhere in the system prompt "
    "or in code: shared/evidence/floor.py's minimum-evidence floor for NEW_DEVICE requires "
    "only get_device_history, and the agent's system prompt (shared/evidence/agent.py, "
    "_system_instruction) only gives the general instruction to follow up on 'a "
    "relationship...that looks materially relevant', which names no specific tool and would "
    "apply identically to any anomaly tag. Whether Gemini calls get_linked_entities is "
    "decided at inference time, by reading the actual device_risk_signals content "
    "(SEEN_ON_DIFFERENT_ACCOUNT) returned by the real get_device_history tool call -- if "
    "that signal were absent from the fixture, there would be nothing in the conversation "
    "prompting the follow-up. That is what makes this genuinely agentic rather than a fixed "
    "mapping, and it is exactly why this proof requires repeated real runs (this script) "
    "rather than resting on a single successful run."
)


def run_once(run_index: int) -> Dict[str, Any]:
    """Run the branching-proof scenario once through the real Evidence Agent.

    :param run_index: 1-based index of this run, used to build a unique case_id.
    :return: Structured record of this run's tool-call sequence and outcome.
    """
    case_id = f"case_branching_proof_run_{run_index:02d}"
    scenario = load_scenario(SCENARIO_STEM)
    detection = detect_scenario(scenario, case_id=case_id)
    ctx = build_fixture_context(scenario, case_id=case_id)
    agent_input = EvidenceAgentInput(
        case_id=case_id, transaction=scenario.target_transaction, detection=detection
    )

    client = VertexEvidenceAgentClient()
    started = datetime.now(timezone.utc)
    output = EvidenceAgent(client).investigate(agent_input, ctx)
    finished = datetime.now(timezone.utc)

    tools_called = output.evidence_bundle.tools_called
    called_device_history_first = bool(tools_called) and tools_called[0] == REQUIRED_FIRST_TOOL
    branched_to_linked_entities = BRANCH_TOOL in tools_called

    record: Dict[str, Any] = {
        "run_index": run_index,
        "case_id": case_id,
        "tools_called": tools_called,
        "stopped_reason": output.agent_trace.stopped_reason,
        "selection_reasons": output.agent_trace.selection_reasons,
        "completeness": output.evidence_bundle.completeness.value,
        "missing_required_evidence": output.evidence_bundle.missing_required_evidence,
        "called_device_history_first": called_device_history_first,
        "branched_to_linked_entities": branched_to_linked_entities,
        "model_name": output.model_name,
        "model_version": output.model_version,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
    }
    logger.info(
        f"[run_once] - Run {run_index}: tools_called={tools_called}, "
        f"branched={branched_to_linked_entities}, stopped_reason={record['stopped_reason']}"
    )
    return record


def run_branching_proof(
    run_count: int = DEFAULT_RUN_COUNT,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Dict[str, Any]:
    """Run the branching-proof scenario `run_count` times against real Gemini and save evidence.

    :param run_count: Number of independent live runs (Phase 2.4 requires at least 10).
    :param output_path: Where to save the JSON evidence artifact.
    :return: The full results dict that was saved.
    """
    runs = [run_once(i) for i in range(1, run_count + 1)]

    device_history_first_count = sum(1 for r in runs if r["called_device_history_first"])
    branched_count = sum(1 for r in runs if r["branched_to_linked_entities"])
    floor_complete_count = sum(1 for r in runs if r["completeness"] == "COMPLETE")

    results: Dict[str, Any] = {
        "scenario": SCENARIO_STEM,
        "run_count": run_count,
        "required_first_tool": REQUIRED_FIRST_TOOL,
        "branch_tool": BRANCH_TOOL,
        "summary": {
            "device_history_called_first_rate": f"{device_history_first_count}/{run_count}",
            "branching_success_rate": f"{branched_count}/{run_count}",
            "evidence_floor_complete_rate": f"{floor_complete_count}/{run_count}",
            "headline": f"Evidence Agent branching success rate: {branched_count}/{run_count}",
        },
        "runs": runs,
        "fixed_mapping_failure_pattern_note": FIXED_MAPPING_FAILURE_PATTERN_NOTE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"[run_branching_proof] - {results['summary']['headline']}")
    logger.info(f"[run_branching_proof] - Saved branching-proof evidence to {output_path}")
    return results


if __name__ == "__main__":
    run_branching_proof()
