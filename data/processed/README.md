# Processed Data: Train & Held-Out Splits

This directory contains the reproducible, stratified 80/20 train/held-out evaluation splits generated from `data/raw/creditcard.csv` per Phase 1.1 of the Sentinel V1 Build Checklist.

---

## 1. Split Configuration & Provenance
- **Raw Dataset Source:** `data/raw/creditcard.csv` (SHA256: `33a178be65174943a07d1736acf5898f6c8e1fa80950dbbe598c17eda968ec59`)
- **Generation Script:** `scripts/split_dataset.py`
- **Random Seed:** `42` (`sklearn.model_selection.train_test_split`)
- **Split Ratio:** 80% Training / 20% Held-Out Evaluation
- **Stratification:** Stratified on target column `Class` to preserve exact class distribution given extreme imbalance
- **Shuffle:** True

---

## 2. Split Summary & Class Distribution

| Partition | Filename | Rows | Legit (`0`) | Fraud (`1`) | Fraud Ratio | % of Dataset |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Training (80%)** | `train.csv` | 227,845 | 227,451 | 394 | 0.1729% | 80.00% |
| **Held-Out (20%)** | `held_out.csv` | 56,962 | 56,864 | 98 | 0.1720% | 20.00% |
| **Total (100%)** | `creditcard.csv` | 284,807 | 284,315 | 492 | 0.1727% | 100.00% |

---

## 3. Leakage Prevention Guarantees
- **Strict Disjoint Partitions:** `train_indices ∩ held_out_indices = ∅` (zero overlapping rows/indices).
- **Sum Integrity:** `227,845 + 56,962 = 284,807` total rows; `394 + 98 = 492` fraud transactions.
- **Held-Out Isolation:** The held-out evaluation split (`held_out.csv`) is strictly reserved for Phase 1.2 baseline evaluation and must **never** be accessed during model training, feature fitting, or fixture seeding.
- **Raw Data Immutability:** `data/raw/creditcard.csv` was verified read-only and remains identical in SHA256 checksum and byte count before and after the split process.

---

## 4. Feature Normalization & Detection Representation
The raw transaction columns are cleaned and normalized via `scripts/preprocess.py` into a 33-feature numeric representation compatible with Sentinel detection models:
- **`amount_scaled`**: Z-score standardized using training mean (`88.1763`) and std (`250.7226`).
- **`amount_log1p`**: `log(1 + Amount)` to handle heavy-tailed monetary values.
- **`hour_of_day`**: Cyclical hour integer `[0..23]` derived as `(Time // 3600) % 24`.
- **`time_sin`** / **`time_cos`**: Continuous cyclic trigonometric encoding `sin(2π·hour/24)` and `cos(2π·hour/24)`.
- **`V1` – `V28`**: 28 continuous PCA latent components (imputed with training medians if null).
- **Target `Class`**: Preserved strictly as separate target series (`y_train.csv`, `y_held_out.csv`).

All statistical parameters were fitted **exclusively on the training split** and exported to `preprocessor_params.json`. Held-out data is transformed strictly via the frozen preprocessor.

---

## 5. Storage & Git Policy
- The large CSV data files (`train.csv`, `held_out.csv`, `X_train.parquet`, etc.) are excluded from Git via `.gitignore`.
- Structured metadata (`split_metadata.json`, `feature_mapping.json`, `preprocessor_params.json`) is version-controlled for automated reproducibility.
