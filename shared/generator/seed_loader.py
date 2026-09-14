"""Deterministic loader for the Phase 1.4 seed fixtures committed under data/seed/.

Fixtures were generated once (scripts/export_seed_fixtures.py) from the seeded
synthetic generator and committed as static JSON. Loading them here is pure
deserialization -- no randomness, no regeneration -- so repeated loads of the
same files always produce byte-identical results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from shared.generator.models import CustomerProfile, MerchantProfile, ScenarioResult

DEFAULT_SEED_DIR = Path("data/seed")


def load_manifest(seed_dir: Path = DEFAULT_SEED_DIR) -> Dict[str, Any]:
    """Load the seed manifest (seed value, customer/merchant counts, scenario index).

    :param seed_dir: Root directory containing the committed seed fixtures.
    :return: Parsed manifest dictionary.
    """
    manifest_path = seed_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"[load_manifest] - Seed manifest missing at {manifest_path}. "
            "Run scripts/export_seed_fixtures.py first."
        )
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_customers(seed_dir: Path = DEFAULT_SEED_DIR) -> List[CustomerProfile]:
    """Load the committed customer roster.

    :param seed_dir: Root directory containing the committed seed fixtures.
    :return: List of validated CustomerProfile instances.
    """
    path = seed_dir / "customers.json"
    if not path.exists():
        raise FileNotFoundError(f"[load_customers] - Seed customers file missing at {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [CustomerProfile.model_validate(item) for item in raw]


def load_merchants(seed_dir: Path = DEFAULT_SEED_DIR) -> List[MerchantProfile]:
    """Load the committed merchant roster.

    :param seed_dir: Root directory containing the committed seed fixtures.
    :return: List of validated MerchantProfile instances.
    """
    path = seed_dir / "merchants.json"
    if not path.exists():
        raise FileNotFoundError(f"[load_merchants] - Seed merchants file missing at {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [MerchantProfile.model_validate(item) for item in raw]


def load_scenario(name: str, seed_dir: Path = DEFAULT_SEED_DIR) -> ScenarioResult:
    """Load one committed scenario fixture by its file stem (e.g. 'branching_proof').

    :param name: Scenario file stem, matching a data/seed/scenarios/<name>.json file.
    :param seed_dir: Root directory containing the committed seed fixtures.
    :return: Validated ScenarioResult instance.
    """
    path = seed_dir / "scenarios" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"[load_scenario] - Seed scenario file missing at {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return ScenarioResult.model_validate(raw)


def load_all_scenarios(seed_dir: Path = DEFAULT_SEED_DIR) -> Dict[str, ScenarioResult]:
    """Load every committed Phase 1.4 scenario fixture, keyed by file stem.

    :param seed_dir: Root directory containing the committed seed fixtures.
    :return: Mapping of scenario file stem to its validated ScenarioResult.
    """
    manifest = load_manifest(seed_dir)
    scenario_files: Dict[str, str] = manifest["scenarios"]
    return {stem: load_scenario(stem, seed_dir) for stem in scenario_files}
