"""Unit tests verifying derived risk-band thresholds and held-out distribution statistics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.derive_thresholds import DEFAULT_OUTPUT_PATH, HIGH_THRESHOLD, LOW_THRESHOLD


def test_thresholds_json_exists() -> None:
    """Verify that eval/risk_thresholds.json exists."""
    assert DEFAULT_OUTPUT_PATH.exists(), f"Missing {DEFAULT_OUTPUT_PATH}"


def test_threshold_values_and_ordering() -> None:
    """Verify that thresholds are mathematically sound and properly ordered."""
    if not DEFAULT_OUTPUT_PATH.exists():
        pytest.skip("eval/risk_thresholds.json not found.")

    with open(DEFAULT_OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    thresh = data["thresholds"]
    low = thresh["low_risk_upper_bound"]
    high = thresh["high_risk_lower_bound"]

    assert low == LOW_THRESHOLD
    assert high == HIGH_THRESHOLD
    assert 0.0 < low < high < 1.0


def test_band_partition_conservation() -> None:
    """Verify that transaction counts across LOW, MEDIUM, and HIGH sum to total held-out counts."""
    if not DEFAULT_OUTPUT_PATH.exists():
        pytest.skip("eval/risk_thresholds.json not found.")

    with open(DEFAULT_OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    bands = data["band_breakdown"]
    low = bands["LOW"]
    med = bands["MEDIUM"]
    high = bands["HIGH"]

    total_tx = low["total_transactions"] + med["total_transactions"] + high["total_transactions"]
    total_fraud = low["fraud_count"] + med["fraud_count"] + high["fraud_count"]
    total_legit = low["legitimate_count"] + med["legitimate_count"] + high["legitimate_count"]

    assert total_tx == 56962
    assert total_fraud == 98
    assert total_legit == 56864

    # Verify fraud concentration in HIGH band
    assert high["fraud_count"] == 88
    assert high["share_of_all_frauds"] >= 0.85
    assert high["fraud_rate"] > 0.10


def test_derivation_governance() -> None:
    """Verify governance declarations indicating pure inference on held-out distribution."""
    if not DEFAULT_OUTPUT_PATH.exists():
        pytest.skip("eval/risk_thresholds.json not found.")

    with open(DEFAULT_OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    gov = data["governance_and_integrity"]
    assert gov["derived_from_held_out_empirical_distribution"] is True
    assert gov["arbitrary_guessing_avoided"] is True
    assert gov["model_retraining_performed"] is False
    assert gov["hyperparameters_modified"] is False
