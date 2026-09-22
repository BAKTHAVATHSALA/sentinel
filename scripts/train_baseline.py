"""Train Sentinel detection baseline model using real fraud training data.

Guarantees:
- Uses ONLY data/processed/X_train.parquet and data/processed/y_train.csv.
- Held-out data is NEVER accessed for training, tuning, or threshold derivation.
- Fixed random seed (42) for deterministic reproducibility.
- Saves model artifact to models/sentinel_baseline_model.joblib (excluded from Git).
- Records comprehensive metadata to models/model_metadata.json.
- Leaves existing shared/detection API intact.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from scripts.lineage import compute_file_sha256

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_baseline")

# Constants
DEFAULT_X_TRAIN_PATH = Path("data/processed/X_train.parquet")
DEFAULT_Y_TRAIN_PATH = Path("data/processed/y_train.csv")
DEFAULT_MODELS_DIR = Path("models")
MODEL_FILENAME = "sentinel_baseline_model.joblib"
METADATA_FILENAME = "model_metadata.json"

MODEL_NAME = "sentinel-detection-baseline"
MODEL_VERSION = "v1.0.0"
RANDOM_SEED = 42
MAX_ITER = 1000
SOLVER = "lbfgs"
C_PARAM = 1.0
CLASS_WEIGHT = "balanced"


def train_detection_baseline(
    x_train_path: Path = DEFAULT_X_TRAIN_PATH,
    y_train_path: Path = DEFAULT_Y_TRAIN_PATH,
    models_dir: Path = DEFAULT_MODELS_DIR,
    random_seed: int = RANDOM_SEED,
) -> Dict[str, Any]:
    """Train deterministic scikit-learn baseline model on training partition only.

    Args:
        x_train_path: Path to X_train.parquet.
        y_train_path: Path to y_train.csv.
        models_dir: Directory to save model artifact and metadata.
        random_seed: Random state seed.

    Returns:
        Dictionary of model metadata, training parameters, and training metrics.
    """
    if not x_train_path.exists():
        raise FileNotFoundError(f"[train_detection_baseline] - Training features missing at {x_train_path}")
    if not y_train_path.exists():
        raise FileNotFoundError(f"[train_detection_baseline] - Training labels missing at {y_train_path}")

    # Guard: ensure held_out files are NOT passed
    if "held_out" in str(x_train_path).lower() or "held_out" in str(y_train_path).lower():
        raise ValueError("[train_detection_baseline] - Data leakage prevented! Held-out data cannot be used for training.")

    # 1. Verify training data integrity and compute hashes
    x_train_sha256 = compute_file_sha256(x_train_path)
    y_train_sha256 = compute_file_sha256(y_train_path)

    logger.info(f"[train_detection_baseline] - X_train SHA256: {x_train_sha256}")
    logger.info(f"[train_detection_baseline] - y_train SHA256: {y_train_sha256}")

    # 2. Load training data
    X_train = pd.read_parquet(x_train_path)
    y_train_df = pd.read_csv(y_train_path)
    y_train = y_train_df["Class"].astype(int)

    num_rows, num_features = X_train.shape
    feature_names = list(X_train.columns)

    legit_count = int((y_train == 0).sum())
    fraud_count = int((y_train == 1).sum())
    fraud_ratio = fraud_count / num_rows

    logger.info(
        f"[train_detection_baseline] - Loaded {num_rows} rows × {num_features} features. "
        f"Legit: {legit_count}, Fraud: {fraud_count} ({fraud_ratio:.6%})"
    )

    # 3. Instantiate model with fixed seed and defensible parameters
    model = LogisticRegression(
        C=C_PARAM,
        solver=SOLVER,
        max_iter=MAX_ITER,
        class_weight=CLASS_WEIGHT,
        random_state=random_seed,
    )

    # 4. Fit model strictly on training data
    logger.info("[train_detection_baseline] - Fitting LogisticRegression...")
    start_time = time.perf_counter()
    model.fit(X_train, y_train)
    training_duration_sec = time.perf_counter() - start_time
    logger.info(f"[train_detection_baseline] - Model fit complete in {training_duration_sec:.2f}s")

    # 5. Compute training-set performance metrics (training evaluation only)
    train_probs = model.predict_proba(X_train)[:, 1]
    train_preds = model.predict(X_train)

    train_accuracy = float(accuracy_score(y_train, train_preds))
    train_roc_auc = float(roc_auc_score(y_train, train_probs))
    train_recall = float(recall_score(y_train, train_preds, zero_division=0))
    train_precision = float(precision_score(y_train, train_preds, zero_division=0))
    train_brier = float(brier_score_loss(y_train, train_probs))

    logger.info(
        f"[train_detection_baseline] - Training Metrics: "
        f"Accuracy: {train_accuracy:.4f}, ROC-AUC: {train_roc_auc:.4f}, "
        f"Fraud Recall: {train_recall:.4f}, Fraud Precision: {train_precision:.4f}"
    )

    # 6. Save model artifact outside Git
    models_dir.mkdir(parents=True, exist_ok=True)
    model_artifact_path = models_dir / MODEL_FILENAME
    joblib.dump(model, model_artifact_path)
    logger.info(f"[train_detection_baseline] - Saved model artifact to {model_artifact_path}")

    # 7. Build and serialize metadata
    metadata: Dict[str, Any] = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_type": "sklearn.linear_model.LogisticRegression",
        "saved_artifact_path": str(model_artifact_path.as_posix()),
        "saved_artifact_size_bytes": model_artifact_path.stat().st_size,
        "hyperparameters": {
            "C": C_PARAM,
            "penalty": "l2",
            "solver": SOLVER,
            "max_iter": MAX_ITER,
            "class_weight": CLASS_WEIGHT,
            "random_state": random_seed,
        },
        "feature_count": num_features,
        "feature_names": feature_names,
        "training_data": {
            "X_train_path": str(x_train_path.as_posix()),
            "X_train_sha256": x_train_sha256,
            "y_train_path": str(y_train_path.as_posix()),
            "y_train_sha256": y_train_sha256,
            "total_rows": num_rows,
            "legitimate_count": legit_count,
            "fraud_count": fraud_count,
            "fraud_ratio": fraud_ratio,
        },
        "training_performance": {
            "accuracy": train_accuracy,
            "roc_auc": train_roc_auc,
            "fraud_recall": train_recall,
            "fraud_precision": train_precision,
            "brier_score": train_brier,
            "training_duration_seconds": round(training_duration_sec, 3),
        },
        "leakage_verification": {
            "training_data_only": True,
            "held_out_data_accessed": False,
            "held_out_evaluated": False,
        },
    }

    metadata_path = models_dir / METADATA_FILENAME
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"[train_detection_baseline] - Saved metadata to {metadata_path}")
    return metadata


if __name__ == "__main__":
    train_detection_baseline()
