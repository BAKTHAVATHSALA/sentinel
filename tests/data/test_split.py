"""Unit tests verifying dataset split integrity and zero-leakage constraints."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.split_dataset import (
    DEFAULT_PROCESSED_DIR,
    DEFAULT_RAW_PATH,
    RANDOM_SEED,
    TARGET_COLUMN,
    compute_file_sha256,
)


def test_split_metadata_validity() -> None:
    """Verify that split_metadata.json exists and records correct dimensions and zero leakage."""
    metadata_path = DEFAULT_PROCESSED_DIR / "split_metadata.json"
    assert metadata_path.exists(), f"Metadata file missing at {metadata_path}"

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["split_configuration"]["random_seed"] == RANDOM_SEED
    assert meta["split_configuration"]["test_size"] == 0.20
    assert meta["split_configuration"]["stratified"] is True

    assert meta["total_rows"] == 284807
    assert meta["total_columns"] == 31

    # Raw counts
    assert meta["raw_distribution"]["legitimate_count"] == 284315
    assert meta["raw_distribution"]["fraud_count"] == 492

    # Train counts (80%)
    train = meta["train_set"]
    assert train["total_rows"] == 227845
    assert train["legitimate_count"] == 227451
    assert train["fraud_count"] == 394

    # Held-out counts (20%)
    held_out = meta["held_out_set"]
    assert held_out["total_rows"] == 56962
    assert held_out["legitimate_count"] == 56864
    assert held_out["fraud_count"] == 98

    # Sum checks
    assert train["total_rows"] + held_out["total_rows"] == meta["total_rows"]
    assert train["fraud_count"] + held_out["fraud_count"] == meta["raw_distribution"]["fraud_count"]
    assert train["legitimate_count"] + held_out["legitimate_count"] == meta["raw_distribution"]["legitimate_count"]

    # Leakage check
    assert meta["leakage_verification"]["index_overlap_count"] == 0
    assert meta["leakage_verification"]["leakage_detected"] is False
    assert meta["leakage_verification"]["raw_file_unchanged"] is True


def test_processed_files_on_disk() -> None:
    """Verify train.csv and held_out.csv row counts, columns, and zero nulls."""
    train_path = DEFAULT_PROCESSED_DIR / "train.csv"
    held_out_path = DEFAULT_PROCESSED_DIR / "held_out.csv"

    if not train_path.exists() or not held_out_path.exists():
        pytest.skip("Processed CSV files not present on disk in this environment.")

    train_df = pd.read_csv(train_path)
    held_out_df = pd.read_csv(held_out_path)

    assert train_df.shape == (227845, 31)
    assert held_out_df.shape == (56962, 31)

    assert TARGET_COLUMN in train_df.columns
    assert TARGET_COLUMN in held_out_df.columns

    assert train_df.isna().sum().sum() == 0
    assert held_out_df.isna().sum().sum() == 0

    assert (train_df[TARGET_COLUMN] == 1).sum() == 394
    assert (train_df[TARGET_COLUMN] == 0).sum() == 227451

    assert (held_out_df[TARGET_COLUMN] == 1).sum() == 98
    assert (held_out_df[TARGET_COLUMN] == 0).sum() == 56864


def test_raw_data_sha256_unmodified() -> None:
    """Verify that the raw dataset file matches the recorded SHA-256."""
    if not DEFAULT_RAW_PATH.exists():
        pytest.skip("Raw creditcard.csv not found.")

    current_hash = compute_file_sha256(DEFAULT_RAW_PATH)
    assert current_hash == "33a178be65174943a07d1736acf5898f6c8e1fa80950dbbe598c17eda968ec59"
