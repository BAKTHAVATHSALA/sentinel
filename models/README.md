# Sentinel Detection Baseline Model

This directory contains metadata and documentation for the Sentinel detection baseline model trained on real card transaction fraud data per Phase 1.1 of the Sentinel V1 Build Checklist.

---

## 1. Model Summary
- **Model Name:** `sentinel-detection-baseline`
- **Model Version:** `v1.0.0`
- **Model Type:** `sklearn.linear_model.LogisticRegression`
- **Trained Artifact Location:** `models/sentinel_baseline_model.joblib` (excluded from Git via `.gitignore`)
- **Training Script:** `scripts/train_baseline.py`
- **Random Seed:** `42` (deterministic reproducibility)

---

## 2. Hyperparameters
```json
{
  "C": 1.0,
  "penalty": "l2",
  "solver": "lbfgs",
  "max_iter": 1000,
  "class_weight": "balanced",
  "random_state": 42
}
```
*Note: `class_weight="balanced"` adjusts loss weights inversely proportional to class frequencies to handle the severe 0.17% fraud class imbalance without guessing all zeros.*

---

## 3. Training Data Provenance & Lineage
- **Feature Matrix:** `data/processed/X_train.parquet`
  - SHA-256: `2fea9a725c50e8950e7c6857629958a54d98b5a57e01e2ecb2fe9496e3f546e1`
  - Dimensions: 227,845 rows × 33 features
- **Target Vector:** `data/processed/y_train.csv`
  - SHA-256: `358fd9ed777fe8972dadf225f366da33fc61379e5b17dbcb559b59a5400e2d72`
  - Distribution: 227,451 legitimate (`Class=0`), 394 fraud (`Class=1`) (0.1729% fraud)

---

## 4. Leakage Prevention & Guardrails
- **Training Data Only:** Model fitting, feature scaling, and parameter optimization used **exclusively** the training partition.
- **Zero Held-Out Exposure:** `data/processed/X_held_out.parquet` and `data/processed/y_held_out.csv` were **never loaded, inspected, or evaluated**.
- **No Threshold Derivation:** Risk band thresholds have not been derived on held-out data yet (deferred to Phase 1.2 evaluation checklist item).

---

## 5. Training Set Performance Baseline
- **Training Accuracy:** 97.48%
- **Training ROC-AUC:** 0.9900
- **Training Fraud Recall:** 92.64% (365 / 394 training frauds detected)
- **Training Brier Score:** 0.0236
- **Training Duration:** 4.86 seconds
