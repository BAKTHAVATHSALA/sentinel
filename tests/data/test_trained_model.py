"""Unit tests for trained Sentinel detection baseline model artifact and metadata."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from scripts.train_baseline import (
    DEFAULT_MODELS_DIR,
    METADATA_FILENAME,
    MODEL_FILENAME,
    MODEL_NAME,
    MODEL_VERSION,
    train_detection_baseline,
)


def test_model_artifact_and_metadata_exist() -> None:
    """Verify that the model artifact and metadata JSON exist on disk."""
    model_path = DEFAULT_MODELS_DIR / MODEL_FILENAME
    metadata_path = DEFAULT_MODELS_DIR / METADATA_FILENAME

    assert model_path.exists(), f"Model artifact missing at {model_path}"
    assert metadata_path.exists(), f"Model metadata missing at {metadata_path}"


def test_model_metadata_contents() -> None:
    """Verify that model_metadata.json captures required model specifications and provenance."""
    metadata_path = DEFAULT_MODELS_DIR / METADATA_FILENAME
    if not metadata_path.exists():
        pytest.skip("model_metadata.json not found.")

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["model_name"] == MODEL_NAME
    assert meta["model_version"] == MODEL_VERSION
    assert meta["model_type"] == "sklearn.linear_model.LogisticRegression"
    assert meta["feature_count"] == 33
    assert len(meta["feature_names"]) == 33

    # Hyperparameters
    params = meta["hyperparameters"]
    assert params["C"] == 1.0
    assert params["solver"] == "lbfgs"
    assert params["class_weight"] == "balanced"
    assert params["random_state"] == 42

    # Training data lineage
    train_data = meta["training_data"]
    assert train_data["total_rows"] == 227845
    assert train_data["legitimate_count"] == 227451
    assert train_data["fraud_count"] == 394
    assert "sha256" in train_data["X_train_sha256"] or len(train_data["X_train_sha256"]) == 64

    # Leakage verification
    leakage = meta["leakage_verification"]
    assert leakage["training_data_only"] is True
    assert leakage["held_out_data_accessed"] is False
    assert leakage["held_out_evaluated"] is False


def test_loaded_model_inference_sanity() -> None:
    """Verify that the serialized joblib artifact loads and evaluates probability outputs correctly."""
    model_path = DEFAULT_MODELS_DIR / MODEL_FILENAME
    if not model_path.exists():
        pytest.skip("Model artifact missing.")

    model: LogisticRegression = joblib.load(model_path)
    assert isinstance(model, LogisticRegression)
    assert model.n_features_in_ == 33

    # Predict on 3 dummy samples with valid feature names
    dummy_X = pd.DataFrame(np.zeros((3, 33), dtype=np.float64), columns=model.feature_names_in_)
    probs = model.predict_proba(dummy_X)

    assert probs.shape == (3, 2)
    assert np.allclose(probs.sum(axis=1), 1.0)
    assert np.all((probs >= 0.0) & (probs <= 1.0))


def test_leakage_guard_rejects_held_out_path(tmp_path: Path) -> None:
    """Verify that train_detection_baseline strictly rejects any input containing held_out."""
    dummy_x = tmp_path / "held_out_features.parquet"
    dummy_y = tmp_path / "y_train.csv"

    dummy_x.touch()
    dummy_y.touch()

    with pytest.raises(ValueError, match="Data leakage prevented"):
        train_detection_baseline(x_train_path=dummy_x, y_train_path=dummy_y)
