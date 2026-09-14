"""Unit tests for Phase 1.4 seed/fixture data committed under data/seed/."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.contracts.detection import AnomalyTag, RiskBand
from shared.detection import detect_scenario
from shared.generator import generate_scenario
from shared.generator.models import CustomerProfile, MerchantProfile, ScenarioResult
from shared.generator.seed_loader import (
    DEFAULT_SEED_DIR,
    load_all_scenarios,
    load_customers,
    load_manifest,
    load_merchants,
    load_scenario,
)

REQUIRED_SCENARIO_FILES = {
    "clean_normal": "CLEAN_NORMAL",
    "signature_fraud": "SIGNATURE_FRAUD",
    "branching_proof": "BRANCHING_PROOF",
    "partial_evidence": "PARTIAL_EVIDENCE",
    "merchant_risk_trend": "MERCHANT_RISK_TREND",
}


def test_seed_directory_contains_all_required_files() -> None:
    """1. Verify manifest, customers, merchants, and all 5 scenario files exist on disk."""
    assert (DEFAULT_SEED_DIR / "manifest.json").exists()
    assert (DEFAULT_SEED_DIR / "customers.json").exists()
    assert (DEFAULT_SEED_DIR / "merchants.json").exists()
    for stem in REQUIRED_SCENARIO_FILES:
        assert (DEFAULT_SEED_DIR / "scenarios" / f"{stem}.json").exists()


def test_manifest_declares_fixed_seed_and_scenario_index() -> None:
    """2. Verify the manifest records the fixed seed value and indexes all 5 scenarios."""
    manifest = load_manifest()
    assert manifest["seed_value"] == 42
    assert manifest["scenario_count"] == 5
    assert set(manifest["scenarios"].keys()) == set(REQUIRED_SCENARIO_FILES.keys())


def test_customer_and_merchant_rosters_load_as_valid_models() -> None:
    """3. Verify committed customers/merchants roundtrip into valid, non-empty rosters."""
    customers = load_customers()
    merchants = load_merchants()

    assert 3 <= len(customers)
    assert 3 <= len(merchants) <= 5
    assert all(isinstance(c, CustomerProfile) for c in customers)
    assert all(isinstance(m, MerchantProfile) for m in merchants)


def test_merchant_roster_includes_a_rising_fraud_trend_merchant() -> None:
    """4. Verify at least one committed merchant has a RISING fraud-report trend."""
    merchants = load_merchants()
    rising = [m for m in merchants if m.fraud_report_trend.value == "RISING"]
    assert len(rising) >= 1


@pytest.mark.parametrize("stem", list(REQUIRED_SCENARIO_FILES.keys()))
def test_loaded_scenario_matches_live_generator_output(stem: str) -> None:
    """5. Verify each committed JSON fixture is byte-for-byte what the deterministic
    generator (seed=42) produces right now -- proving 'loaded deterministically by a
    fixed seed value', not a stale or hand-edited snapshot."""
    loaded = load_scenario(stem)
    live = generate_scenario(REQUIRED_SCENARIO_FILES[stem], seed=42)

    assert isinstance(loaded, ScenarioResult)
    assert loaded.model_dump(mode="json") == live.model_dump(mode="json")


def test_load_scenario_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    """6. Verify the loader fails loudly, never silently, on a missing fixture file."""
    with pytest.raises(FileNotFoundError, match="Seed scenario file missing"):
        load_scenario("does_not_exist", seed_dir=tmp_path)


def test_clean_normal_scenario_has_zero_anomaly_tags() -> None:
    """7. Verify the clean/normal scenario is detection-clean (LOW band, no tags),
    consistent with Policy rule P-005 (AUTO_RESOLVE)."""
    sc = load_scenario("clean_normal")
    out = detect_scenario(sc)

    assert out.anomaly_tags == []
    assert out.risk_band == RiskBand.LOW
    assert sc.metadata["expected_policy_outcome"] == "AUTO_RESOLVE"


def test_signature_fraud_scenario_is_multi_signal_high_risk() -> None:
    """8. Verify the signature fraud scenario fires multiple anomaly signals at HIGH band,
    consistent with an ESCALATE outcome."""
    sc = load_scenario("signature_fraud")
    out = detect_scenario(sc)

    assert len(out.anomaly_tags) >= 2
    assert AnomalyTag.NEW_DEVICE in out.anomaly_tags
    assert AnomalyTag.UNUSUAL_LOCATION in out.anomaly_tags
    assert AnomalyTag.MERCHANT_RISK in out.anomaly_tags
    assert out.risk_band == RiskBand.HIGH


def test_branching_proof_scenario_fires_only_new_device() -> None:
    """9. Verify the branching-proof scenario fires EXACTLY NEW_DEVICE -- no other tag
    would contribute a required tool to the evidence floor."""
    sc = load_scenario("branching_proof")
    out = detect_scenario(sc)

    assert out.anomaly_tags == [AnomalyTag.NEW_DEVICE]


def test_branching_proof_scenario_floor_does_not_require_linked_entities() -> None:
    """10. Verify the branching-proof fixture explicitly documents that NEW_DEVICE's
    minimum-evidence floor (Contracts v1.2 S11.4) is get_device_history only, so any
    later get_linked_entities call is the agent's own choice, not a forced mapping."""
    sc = load_scenario("branching_proof")

    floor = sc.metadata["minimum_evidence_floor_for_new_device"]
    assert floor == ["get_device_history"]
    assert "get_linked_entities" not in floor
    assert sc.metadata["floor_requires_get_linked_entities"] is False


def test_branching_proof_scenario_seeds_device_history_and_linked_entities_fixtures() -> None:
    """11. Verify the fixture data Phase 2's get_device_history/get_linked_entities
    tools will need is present: the shared device was seen on a *different* account 2
    hours earlier, and that account has a recent anomaly."""
    sc = load_scenario("branching_proof")

    device_fixture = sc.metadata["device_history_fixture"]
    assert device_fixture["known_device"] is False
    signal = device_fixture["device_risk_signals"][0]
    assert signal["signal"] == "SEEN_ON_DIFFERENT_ACCOUNT"
    assert signal["hours_before_target"] == 2
    assert signal["other_customer_id"] == sc.secondary_profile.customer_id

    linked_fixture = sc.metadata["linked_entities_fixture"]
    assert sc.secondary_profile.account_id in linked_fixture["linked_accounts"]
    assert len(linked_fixture["recent_anomalies"]) >= 1


def test_partial_evidence_scenario_configures_a_failing_tool() -> None:
    """12. Verify the partial-evidence scenario deliberately marks the sole tool its
    anomaly tag's floor requires as failing, guaranteeing PARTIAL evidence."""
    sc = load_scenario("partial_evidence")
    out = detect_scenario(sc)

    assert out.anomaly_tags == [AnomalyTag.NEW_DEVICE]
    failing_tool = sc.metadata["failing_tool"]
    assert failing_tool["tool_name"] == "get_device_history"
    assert failing_tool["failure_mode"] in {"TIMEOUT", "ERROR"}
    assert sc.metadata["expected_evidence_completeness"] == "PARTIAL"


def test_merchant_risk_trend_scenario_is_single_signal_new_to_customer() -> None:
    """13. Verify the merchant-risk-trend scenario fires only MERCHANT_RISK, at a
    genuinely new-to-customer merchant with a rising fraud-report trend."""
    sc = load_scenario("merchant_risk_trend")
    out = detect_scenario(sc)

    assert out.anomaly_tags == [AnomalyTag.MERCHANT_RISK]
    assert out.risk_band == RiskBand.HIGH
    assert sc.metadata["customer_prior_transactions_with_merchant"] == 0
    assert sc.merchant_profile.fraud_report_trend.value == "RISING"
    assert all(
        tx.merchant_id != sc.merchant_profile.merchant_id for tx in sc.baseline_transactions
    ), "Baseline history must never touch the risky merchant -- it must be genuinely new-to-customer"


def test_load_all_scenarios_returns_every_required_scenario() -> None:
    """14. Verify load_all_scenarios() returns all 5 required, independently loadable scenarios."""
    all_scenarios = load_all_scenarios()
    assert set(all_scenarios.keys()) == set(REQUIRED_SCENARIO_FILES.keys())

    # seeded_demo_case() reports its own internal scenario_name regardless of dispatch alias.
    expected_names = dict(REQUIRED_SCENARIO_FILES, signature_fraud="V1_FLAGSHIP_DEMO_SCENARIO")
    for stem, sc in all_scenarios.items():
        assert isinstance(sc, ScenarioResult)
        assert sc.scenario_name == expected_names[stem]
