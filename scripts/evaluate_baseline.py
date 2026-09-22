"""Evaluate trained Sentinel detection baseline model on held-out dataset.

Guarantees:
- Uses ONLY the existing trained model artifact (models/sentinel_baseline_model.joblib).
- Zero retraining, refitting, or hyperparameter tuning.
- Held-out data is used exclusively for evaluation.
- Computes Precision, Recall, ROC-AUC, PR-AUC, False-Negative Rate (FNR), and confusion matrix.
- Saves evaluation results to eval/detection_baseline.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)

from scripts.lineage import compute_file_sha256

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evaluate_baseline")

# Default file paths
DEFAULT_MODEL_PATH = Path("models/sentinel_baseline_model.joblib")
DEFAULT_X_HELD_OUT_PATH = Path("data/processed/X_held_out.parquet")
DEFAULT_Y_HELD_OUT_PATH = Path("data/processed/y_held_out.csv")
DEFAULT_OUTPUT_JSON_PATH = Path("eval/detection_baseline.json")


def evaluate_detection_baseline(
    model_path: Path = DEFAULT_MODEL_PATH,
    x_held_out_path: Path = DEFAULT_X_HELD_OUT_PATH,
    y_held_out_path: Path = DEFAULT_Y_HELD_OUT_PATH,
    output_path: Path = DEFAULT_OUTPUT_JSON_PATH,
) -> Dict[str, Any]:
    """Evaluate pre-trained baseline model on held-out partition without refitting.

    Args:
        model_path: Path to serialized trained model artifact.
        x_held_out_path: Path to X_held_out.parquet.
        y_held_out_path: Path to y_held_out.csv.
        output_path: Path to save evaluation metrics JSON.

    Returns:
        Dictionary containing all evaluation metrics, confusion matrix, and lineage.
    """
    if not model_path.exists():
        raise FileNotFoundError(f"[evaluate_detection_baseline] - Model artifact missing at {model_path}")
    if not x_held_out_path.exists():
        raise FileNotFoundError(f"[evaluate_detection_baseline] - Held-out features missing at {x_held_out_path}")
    if not y_held_out_path.exists():
        raise FileNotFoundError(f"[evaluate_detection_baseline] - Held-out labels missing at {y_held_out_path}")

    # 1. Compute file hashes for audit lineage
    model_sha256 = compute_file_sha256(model_path)
    x_held_out_sha256 = compute_file_sha256(x_held_out_path)
    y_held_out_sha256 = compute_file_sha256(y_held_out_path)

    # 2. Load model strictly for inference
    model: LogisticRegression = joblib.load(model_path)
    logger.info(f"[evaluate_detection_baseline] - Loaded model {type(model).__name__} (SHA256: {model_sha256})")

    # 3. Load held-out evaluation data
    X_held_out = pd.read_parquet(x_held_out_path)
    y_held_out = pd.read_csv(y_held_out_path)["Class"].astype(int)

    num_rows, num_features = X_held_out.shape
    legit_count = int((y_held_out == 0).sum())
    fraud_count = int((y_held_out == 1).sum())

    logger.info(
        f"[evaluate_detection_baseline] - Evaluating on {num_rows} held-out rows × {num_features} features. "
        f"Legit: {legit_count}, Fraud: {fraud_count} ({fraud_count / num_rows:.6%})"
    )

    # 4. Predict probabilities and classes
    y_probs = model.predict_proba(X_held_out)[:, 1]
    y_preds = model.predict(X_held_out)

    # 5. Compute confusion matrix
    cm = confusion_matrix(y_held_out, y_preds)
    tn, fp, fn, tp = (int(v) for v in cm.ravel())

    # 6. Compute required five metrics
    precision = float(precision_score(y_held_out, y_preds, zero_division=0))
    recall = float(recall_score(y_held_out, y_preds, zero_division=0))
    roc_auc = float(roc_auc_score(y_held_out, y_probs))
    pr_auc = float(average_precision_score(y_held_out, y_probs))
    fnr = float(fn / (tp + fn)) if (tp + fn) > 0 else 0.0

    logger.info(
        f"[evaluate_detection_baseline] - Results: "
        f"Precision: {precision:.6f}, Recall: {recall:.6f}, ROC-AUC: {roc_auc:.6f}, "
        f"PR-AUC: {pr_auc:.6f}, FNR: {fnr:.6f}"
    )
    logger.info(
        f"[evaluate_detection_baseline] - Confusion Matrix: "
        f"TP={tp}, FP={fp}, TN={tn}, FN={fn}"
    )

    # 7. Assemble structured evaluation report
    results: Dict[str, Any] = {
        "model_metadata": {
            "model_type": "sklearn.linear_model.LogisticRegression",
            "model_path": str(model_path.as_posix()),
            "model_sha256": model_sha256,
        },
        "evaluation_dataset": {
            "x_held_out_path": str(x_held_out_path.as_posix()),
            "x_held_out_sha256": x_held_out_sha256,
            "y_held_out_path": str(y_held_out_path.as_posix()),
            "y_held_out_sha256": y_held_out_sha256,
            "total_rows": num_rows,
            "total_features": num_features,
            "legitimate_count": legit_count,
            "fraud_count": fraud_count,
            "fraud_ratio": fraud_count / num_rows,
        },
        "metrics": {
            "precision": precision,
            "recall": recall,
            "roc_auc": roc_auc,
            "pr_auc": pr_auc,
            "false_negative_rate": fnr,
        },
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
        },
        "leakage_and_governance_confirmation": {
            "held_out_data_used_exclusively_for_evaluation": True,
            "model_retraining_performed": False,
            "hyperparameter_tuning_performed": False,
            "feature_engineering_modified": False,
            "risk_bands_derived": False,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"[evaluate_detection_baseline] - Saved baseline evaluation results to {output_path}")
    return results


if __name__ == "__main__":
    evaluate_detection_baseline()
