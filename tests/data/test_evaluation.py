"""Unit tests for baseline model held-out evaluation results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.evaluate_baseline import DEFAULT_OUTPUT_JSON_PATH


def test_baseline_evaluation_json_exists() -> None:
    """Verify that eval/detection_baseline.json exists."""
    assert DEFAULT_OUTPUT_JSON_PATH.exists(), f"Missing {DEFAULT_OUTPUT_JSON_PATH}"


def test_baseline_evaluation_metrics() -> None:
    """Verify evaluation metric values and mathematical relationships."""
    if not DEFAULT_OUTPUT_JSON_PATH.exists():
        pytest.skip("eval/detection_baseline.json not found.")

    with open(DEFAULT_OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    metrics = data["metrics"]
    precision = metrics["precision"]
    recall = metrics["recall"]
    roc_auc = metrics["roc_auc"]
    pr_auc = metrics["pr_auc"]
    fnr = metrics["false_negative_rate"]

    # Bounds and sanity
    assert 0.0 < precision < 1.0
    assert 0.0 < recall < 1.0
    assert roc_auc >= 0.95, f"Expected high ROC-AUC, got {roc_auc}"
    assert pr_auc >= 0.60, f"Expected high PR-AUC, got {pr_auc}"
    assert 0.0 < fnr < 1.0

    # Complementarity: Recall + FNR == 1.0
    assert pytest.approx(recall + fnr, abs=1e-7) == 1.0


def test_confusion_matrix_conservation() -> None:
    """Verify that confusion matrix counts match held-out dataset distributions."""
    if not DEFAULT_OUTPUT_JSON_PATH.exists():
        pytest.skip("eval/detection_baseline.json not found.")

    with open(DEFAULT_OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cm = data["confusion_matrix"]
    tp = cm["true_positives"]
    fp = cm["false_positives"]
    tn = cm["true_negatives"]
    fn = cm["false_negatives"]

    eval_data = data["evaluation_dataset"]
    total_rows = eval_data["total_rows"]
    fraud_count = eval_data["fraud_count"]
    legit_count = eval_data["legitimate_count"]

    assert total_rows == 56962
    assert fraud_count == 98
    assert legit_count == 56864

    # Conservation checks
    assert tp + fn == fraud_count, f"TP + FN ({tp + fn}) != {fraud_count}"
    assert tn + fp == legit_count, f"TN + FP ({tn + fp}) != {legit_count}"
    assert tp + fp + tn + fn == total_rows


def test_governance_and_leakage_declarations() -> None:
    """Verify that evaluation was pure inference without retraining or band derivation."""
    if not DEFAULT_OUTPUT_JSON_PATH.exists():
        pytest.skip("eval/detection_baseline.json not found.")

    with open(DEFAULT_OUTPUT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    gov = data["leakage_and_governance_confirmation"]
    assert gov["held_out_data_used_exclusively_for_evaluation"] is True
    assert gov["model_retraining_performed"] is False
    assert gov["hyperparameter_tuning_performed"] is False
    assert gov["feature_engineering_modified"] is False
    assert gov["risk_bands_derived"] is False
