"""Unit tests for TransactionFeaturePreprocessor and dataset feature normalization."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.preprocess import (
    DEFAULT_PROCESSED_DIR,
    NUM_PCA_COMPONENTS,
    TARGET_COLUMN,
    TransactionFeaturePreprocessor,
)


def test_preprocessor_parameters_exist() -> None:
    """Verify that fitted parameters and feature mapping JSON files exist and are valid."""
    params_path = DEFAULT_PROCESSED_DIR / "preprocessor_params.json"
    mapping_path = DEFAULT_PROCESSED_DIR / "feature_mapping.json"

    assert params_path.exists(), f"Parameters missing at {params_path}"
    assert mapping_path.exists(), f"Mapping missing at {mapping_path}"

    with open(params_path, "r", encoding="utf-8") as f:
        params = json.load(f)

    assert "amount_mean" in params
    assert "amount_std" in params
    assert "imputation_medians" in params
    assert len(params["feature_names"]) == 33

    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    assert mapping["partitions"]["train"]["rows"] == 227845
    assert mapping["partitions"]["train"]["features"] == 33
    assert mapping["partitions"]["held_out"]["rows"] == 56962
    assert mapping["partitions"]["held_out"]["features"] == 33


def test_preprocessor_serialization_roundtrip(tmp_path: Path) -> None:
    """Verify that saving and reloading preprocessor parameters produces identical results."""
    params_path = DEFAULT_PROCESSED_DIR / "preprocessor_params.json"
    if not params_path.exists():
        pytest.skip("preprocessor_params.json not generated.")

    preprocessor = TransactionFeaturePreprocessor.load_parameters(params_path)
    temp_save_path = tmp_path / "temp_params.json"
    preprocessor.save_parameters(temp_save_path)

    reloaded = TransactionFeaturePreprocessor.load_parameters(temp_save_path)
    assert preprocessor.feature_names == reloaded.feature_names
    assert preprocessor._stats.amount_mean == reloaded._stats.amount_mean
    assert preprocessor._stats.amount_std == reloaded._stats.amount_std


def test_missing_value_imputation_and_transformation() -> None:
    """Verify that missing values in inputs are cleanly imputed with training medians."""
    params_path = DEFAULT_PROCESSED_DIR / "preprocessor_params.json"
    if not params_path.exists():
        pytest.skip("preprocessor_params.json not generated.")

    preprocessor = TransactionFeaturePreprocessor.load_parameters(params_path)

    # Synthetic single-row sample with NaNs in Amount and V1
    sample_df = pd.DataFrame(
        {
            "Time": [7200.0],
            "Amount": [np.nan],
            "V1": [np.nan],
            **{f"V{i}": [0.5] for i in range(2, NUM_PCA_COMPONENTS + 1)},
            TARGET_COLUMN: [0],
        }
    )

    X, y = preprocessor.transform(sample_df)
    assert X.shape == (1, 33)
    assert not X.isna().any().any(), "Imputation failed; NaN remains in features."
    assert y is not None and y.iloc[0] == 0


def test_frozen_preprocessing_held_out_leakage_free() -> None:
    """Verify that held-out split can be transformed with frozen parameters without mutating stats."""
    params_path = DEFAULT_PROCESSED_DIR / "preprocessor_params.json"
    held_out_csv = DEFAULT_PROCESSED_DIR / "held_out.csv"

    if not params_path.exists() or not held_out_csv.exists():
        pytest.skip("Required processed files not present.")

    preprocessor = TransactionFeaturePreprocessor.load_parameters(params_path)
    initial_mean = preprocessor._stats.amount_mean
    initial_std = preprocessor._stats.amount_std

    # Load small subset of held-out
    held_out_df = pd.read_csv(held_out_csv, nrows=100)
    X_ho, y_ho = preprocessor.transform(held_out_df)

    assert X_ho.shape == (100, 33)
    assert y_ho is not None and len(y_ho) == 100

    # Ensure preprocessor stats were NOT mutated by held-out data
    assert preprocessor._stats.amount_mean == initial_mean
    assert preprocessor._stats.amount_std == initial_std


def test_transform_transaction_domain_entity() -> None:
    """Verify that a Sentinel Transaction domain object is cleanly transformed."""
    from datetime import datetime, timezone
    from decimal import Decimal
    from shared.contracts.transaction import (
        AuthorizationStage,
        Channel,
        Direction,
        Geo,
        PaymentRail,
        Transaction,
    )

    params_path = DEFAULT_PROCESSED_DIR / "preprocessor_params.json"
    if not params_path.exists():
        pytest.skip("preprocessor_params.json not generated.")

    preprocessor = TransactionFeaturePreprocessor.load_parameters(params_path)

    tx = Transaction(
        transaction_id="tx_test_preprocess_001",
        customer_id="cust_001",
        account_id="acc_001",
        card_id="card_001",
        merchant_id="merch_001",
        amount=Decimal("150.50"),
        currency="USD",
        timestamp=datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc),
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_001",
        ip_address="192.168.1.1",
        geo=Geo(lat=Decimal("37.7749"), lon=Decimal("-122.4194"), country="US"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )

    X_tx = preprocessor.transform_transaction(tx, latent_pca={"V1": 1.25, "V2": -0.75})
    assert X_tx.shape == (1, 33)
    assert not X_tx.isna().any().any()
    assert X_tx["hour_of_day"].iloc[0] == 14.5
    assert X_tx["V1"].iloc[0] == 1.25
    assert X_tx["V2"].iloc[0] == -0.75
