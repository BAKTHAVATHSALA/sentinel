"""Export deterministic Phase 1.4 seed/fixture data to data/seed/ as versioned JSON.

Generates the five scenarios required by Phase 1.4 of the Sentinel V1 Build
Checklist from the existing seeded synthetic generator (shared/generator) using
a fixed seed, and writes them to data/seed/ as committed, inspectable JSON --
satisfying "Store all fixtures as versioned JSON/YAML files in data/seed/,
loaded deterministically by a fixed seed value". Regenerating with the same
seed reproduces byte-identical output (shared/generator is already covered by
its own reproducibility tests).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from shared.generator import ScenarioResult, generate_scenario

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export_seed_fixtures")

SEED_VALUE = 42
DEFAULT_SEED_DIR = Path("data/seed")

# The five scenarios required by Phase 1.4 of the Sentinel V1 Build Checklist.
REQUIRED_SCENARIOS: Dict[str, str] = {
    "clean_normal": "CLEAN_NORMAL",
    "signature_fraud": "SIGNATURE_FRAUD",
    "branching_proof": "BRANCHING_PROOF",
    "partial_evidence": "PARTIAL_EVIDENCE",
    "merchant_risk_trend": "MERCHANT_RISK_TREND",
}


def export_seed_fixtures(
    seed_dir: Path = DEFAULT_SEED_DIR,
    seed: int = SEED_VALUE,
) -> Dict[str, Any]:
    """Generate and persist all Phase 1.4 seed fixtures deterministically.

    :param seed_dir: Root directory to write fixtures into (data/seed/).
    :param seed: Fixed deterministic seed shared by every generated scenario.
    :return: Summary manifest dictionary (also written to manifest.json).
    """
    scenarios_dir = seed_dir / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    customers: Dict[str, Dict[str, Any]] = {}
    merchants: Dict[str, Dict[str, Any]] = {}
    scenario_files: Dict[str, str] = {}

    for file_stem, scenario_name in REQUIRED_SCENARIOS.items():
        result: ScenarioResult = generate_scenario(scenario_name, seed=seed)
        payload = result.model_dump(mode="json")

        out_path = scenarios_dir / f"{file_stem}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        scenario_files[file_stem] = str(out_path.as_posix())
        logger.info(f"[export_seed_fixtures] - Wrote {out_path} ({scenario_name})")

        customers[result.customer_profile.customer_id] = result.customer_profile.model_dump(mode="json")
        if result.secondary_profile is not None:
            customers[result.secondary_profile.customer_id] = result.secondary_profile.model_dump(mode="json")
        merchants[result.merchant_profile.merchant_id] = result.merchant_profile.model_dump(mode="json")

    customers_path = seed_dir / "customers.json"
    with open(customers_path, "w", encoding="utf-8") as f:
        json.dump(list(customers.values()), f, indent=2)
    logger.info(f"[export_seed_fixtures] - Wrote {customers_path} ({len(customers)} customers)")

    merchants_path = seed_dir / "merchants.json"
    with open(merchants_path, "w", encoding="utf-8") as f:
        json.dump(list(merchants.values()), f, indent=2)
    logger.info(f"[export_seed_fixtures] - Wrote {merchants_path} ({len(merchants)} merchants)")

    manifest: Dict[str, Any] = {
        "seed_value": seed,
        "scenario_count": len(REQUIRED_SCENARIOS),
        "customer_count": len(customers),
        "merchant_count": len(merchants),
        "merchants_with_rising_trend": sorted(
            m["merchant_id"] for m in merchants.values() if m["fraud_report_trend"] == "RISING"
        ),
        "scenarios": scenario_files,
        "customers_file": str(customers_path.as_posix()),
        "merchants_file": str(merchants_path.as_posix()),
    }
    manifest_path = seed_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"[export_seed_fixtures] - Wrote {manifest_path}")

    return manifest


if __name__ == "__main__":
    export_seed_fixtures()
