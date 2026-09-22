"""Deterministic 80/20 train/held-out dataset split for Sentinel fraud detection.

Performs a stratified split of data/raw/creditcard.csv into:
- 80% training set (data/processed/train.csv)
- 20% held-out evaluation set (data/processed/held_out.csv)

Enforces strict zero-leakage constraints, preserves fraud class proportions,
and logs split metadata to data/processed/split_metadata.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from sklearn.model_selection import train_test_split

from scripts.lineage import compute_file_sha256

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("split_dataset")

# Fixed constants for deterministic reproduction
DEFAULT_RAW_PATH = Path("data/raw/creditcard.csv")
DEFAULT_PROCESSED_DIR = Path("data/processed")
RANDOM_SEED: int = 42
TEST_SIZE: float = 0.20
TARGET_COLUMN: str = "Class"


def split_credit_card_dataset(
    raw_path: Path = DEFAULT_RAW_PATH,
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
    test_size: float = TEST_SIZE,
    random_seed: int = RANDOM_SEED,
) -> Dict[str, Any]:
    """Execute stratified, zero-leakage 80/20 split on raw credit card transactions.

    Args:
        raw_path: Path to the raw creditcard.csv file.
        processed_dir: Destination directory for processed splits and metadata.
        test_size: Proportion of dataset allocated to held-out evaluation (0.20 = 20%).
        random_seed: Deterministic random seed for reproducibility.

    Returns:
        Dict containing split metadata, row counts, class distributions, and leakage checks.
    """
    if not raw_path.exists():
        raise FileNotFoundError(f"[split_credit_card_dataset] - Raw dataset not found at {raw_path}")

    # Step 1: Verify raw data integrity before read
    initial_sha256 = compute_file_sha256(raw_path)
    initial_size = raw_path.stat().st_size
    logger.info(f"[split_credit_card_dataset] - Raw dataset SHA256: {initial_sha256} ({initial_size} bytes)")

    # Step 2: Load raw dataset
    df = pd.read_csv(raw_path)
    total_rows, total_cols = df.shape
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"[split_credit_card_dataset] - Target column '{TARGET_COLUMN}' missing in {raw_path}")

    raw_class_counts = df[TARGET_COLUMN].value_counts().to_dict()
    raw_legit = int(raw_class_counts.get(0, 0))
    raw_fraud = int(raw_class_counts.get(1, 0))

    # Step 3: Stratified 80/20 train/held-out split
    train_df, held_out_df = train_test_split(
        df,
        test_size=test_size,
        random_state=random_seed,
        stratify=df[TARGET_COLUMN],
        shuffle=True,
    )

    # Step 4: Strict Leakage Verification
    train_indices = set(train_df.index)
    held_out_indices = set(held_out_df.index)
    overlap = train_indices.intersection(held_out_indices)
    if overlap:
        raise AssertionError(f"[split_credit_card_dataset] - Data leakage detected! {len(overlap)} overlapping indices.")

    if len(train_df) + len(held_out_df) != total_rows:
        raise AssertionError(
            f"[split_credit_card_dataset] - Row count mismatch: {len(train_df)} + {len(held_out_df)} != {total_rows}"
        )

    train_class_counts = train_df[TARGET_COLUMN].value_counts().to_dict()
    held_out_class_counts = held_out_df[TARGET_COLUMN].value_counts().to_dict()

    train_legit = int(train_class_counts.get(0, 0))
    train_fraud = int(train_class_counts.get(1, 0))
    held_out_legit = int(held_out_class_counts.get(0, 0))
    held_out_fraud = int(held_out_class_counts.get(1, 0))

    if (train_legit + held_out_legit) != raw_legit:
        raise AssertionError("[split_credit_card_dataset] - Legitimate class count sum does not match raw.")
    if (train_fraud + held_out_fraud) != raw_fraud:
        raise AssertionError("[split_credit_card_dataset] - Fraud class count sum does not match raw.")

    # Step 5: Save processed splits and metadata
    processed_dir.mkdir(parents=True, exist_ok=True)
    train_path = processed_dir / "train.csv"
    held_out_path = processed_dir / "held_out.csv"
    metadata_path = processed_dir / "split_metadata.json"

    train_df.to_csv(train_path, index=False)
    held_out_df.to_csv(held_out_path, index=False)

    # Step 6: Verify raw data remained strictly untouched
    post_sha256 = compute_file_sha256(raw_path)
    post_size = raw_path.stat().st_size
    if initial_sha256 != post_sha256 or initial_size != post_size:
        raise AssertionError("[split_credit_card_dataset] - Raw data file was modified during split process!")

    metadata: Dict[str, Any] = {
        "dataset_name": "Credit Card Fraud Detection (ULB / OpenML 42175)",
        "raw_file": str(raw_path.as_posix()),
        "raw_sha256": initial_sha256,
        "raw_size_bytes": initial_size,
        "split_configuration": {
            "random_seed": random_seed,
            "test_size": test_size,
            "train_ratio": 1.0 - test_size,
            "stratified": True,
            "stratify_column": TARGET_COLUMN,
            "shuffle": True,
        },
        "total_rows": total_rows,
        "total_columns": total_cols,
        "raw_distribution": {
            "legitimate_count": raw_legit,
            "fraud_count": raw_fraud,
            "fraud_ratio": raw_fraud / total_rows,
        },
        "train_set": {
            "filename": train_path.name,
            "total_rows": len(train_df),
            "legitimate_count": train_legit,
            "fraud_count": train_fraud,
            "fraud_ratio": train_fraud / len(train_df),
            "percentage_of_total": len(train_df) / total_rows,
        },
        "held_out_set": {
            "filename": held_out_path.name,
            "total_rows": len(held_out_df),
            "legitimate_count": held_out_legit,
            "fraud_count": held_out_fraud,
            "fraud_ratio": held_out_fraud / len(held_out_df),
            "percentage_of_total": len(held_out_df) / total_rows,
        },
        "leakage_verification": {
            "index_overlap_count": len(overlap),
            "leakage_detected": False,
            "raw_file_unchanged": True,
        },
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"[split_credit_card_dataset] - Saved train split: {train_path} ({len(train_df)} rows)")
    logger.info(f"[split_credit_card_dataset] - Saved held-out split: {held_out_path} ({len(held_out_df)} rows)")
    logger.info(f"[split_credit_card_dataset] - Saved split metadata: {metadata_path}")
    return metadata


if __name__ == "__main__":
    split_credit_card_dataset()
