"""Phase 4.3: run every seeded scenario through the real, fully-wired
Sentinel V1 pipeline (Build Checklist Phase 4.3 "Run all seeded scenarios
from Phase 1.4 through the full pipeline; confirm each produces the
expected outcome").

Every call below is real: real Gemini Flash (Evidence Agent), real Gemini
Pro (Reasoning), and a real Firestore case store -- nothing here is
scripted or mocked. Each scenario's target_transaction is submitted through
shared.pipeline.orchestrator.run_pipeline() exactly as POST /transactions
would receive it, and the resulting Policy outcome is compared against the
scenario fixture's own `metadata.expected_policy_outcome` where present.
Results are saved to eval/pipeline_scenarios_proof.json.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict

from shared.generator.seed_loader import load_all_scenarios
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client
from shared.pipeline.orchestrator import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_pipeline_scenarios")

DEFAULT_OUTPUT_PATH = Path("eval/pipeline_scenarios_proof.json")


def run_all_scenarios(output_path: Path = DEFAULT_OUTPUT_PATH) -> Dict[str, Any]:
    """Run every committed seed scenario through the real pipeline and save evidence.

    :param output_path: Where to save the JSON evidence artifact.
    :return: The full results dict that was saved.
    """
    store = CaseStore(build_firestore_client())
    scenarios = load_all_scenarios()

    runs = []
    for stem, scenario in sorted(scenarios.items()):
        transaction = scenario.target_transaction
        expected = scenario.metadata.get("expected_policy_outcome")
        started = datetime.now(timezone.utc)
        try:
            result = run_pipeline(transaction, case_store=store)
            error = None
        except Exception as exc:  # noqa: BLE001 -- record failures as evidence, don't crash the sweep
            result = None
            error = repr(exc)
        finished = datetime.now(timezone.utc)

        actual_outcome = result.get("outcome") if result else None
        actual_state = result.get("state") if result else None
        matches_expected = expected is None or actual_outcome == expected or (
            expected == "AUTO_RESOLVE" and actual_state == "AUTO_RESOLVED"
        )

        record = {
            "scenario": stem,
            "transaction_id": transaction.transaction_id,
            "expected_policy_outcome": expected,
            "actual_outcome": actual_outcome,
            "actual_state": actual_state,
            "case_id": result.get("case_id") if result else None,
            "rule_id": result.get("rule_id") if result else None,
            "matches_expected": matches_expected,
            "error": error,
            "duration_seconds": (finished - started).total_seconds(),
        }
        logger.info(
            f"[run_all_scenarios] - {stem}: expected={expected} actual={actual_outcome} "
            f"state={actual_state} matches={matches_expected}"
        )
        runs.append(record)

    all_match = all(r["matches_expected"] and r["error"] is None for r in runs)
    results: Dict[str, Any] = {
        "runs": runs,
        "summary": {
            "total_scenarios": len(runs),
            "all_matched_expected_outcome": all_match,
            "headline": f"Pipeline scenario sweep: all matched expected outcome = {all_match}",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"[run_all_scenarios] - {results['summary']['headline']}")
    logger.info(f"[run_all_scenarios] - Saved pipeline scenario evidence to {output_path}")
    return results


if __name__ == "__main__":
    run_all_scenarios()
