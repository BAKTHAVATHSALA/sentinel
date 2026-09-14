# Sentinel Data Documentation

This document describes the datasets used across Sentinel V1 for training, evaluation, and baseline risk scoring per the Sentinel V1 Build Checklist.

---

## 1. Real Labeled Fraud Dataset

### Dataset Name
**Credit Card Fraud Detection** (ULB Machine Learning Group / Worldline)

### Source & Provenance
- **Primary Source (Kaggle):** [Kaggle - Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
- **OpenML Benchmark:** [OpenML Dataset 42175 (CreditCardFraudDetection)](https://www.openml.org/d/42175)
- **Direct Raw Mirror:** `https://raw.githubusercontent.com/nsethi31/Kaggle-Data-Credit-Card-Fraud-Detection/master/creditcard.csv`
- **Research Citation:** Andrea Dal Pozzolo, Olivier Caelen, Reid A. Johnson, and Gianluca Bontempi. *Calibrating Probability with Undersampling for Unbalanced Classification.* In Symposium on Computational Intelligence and Data Mining (CIDM), IEEE, 2015.
- **Acquisition Date:** 2026-09-14
- **Local Storage Location:** `data/raw/creditcard.csv` (excluded from Git tracking via `.gitignore`)

### License & Usage Terms
- **License:** Open Data Commons Public Domain Dedication and License (PDDL) v1.0 / Database Contents License (DbCL) v1.0.
- **Usage Rights:** Public domain dedication by Université Libre de Bruxelles (ULB) ML Group and Worldline. Fully permitted for research, benchmarking, model training, and commercial experimentation.

### Dataset Size & Volume
- **Raw File Size:** 102,634,230 bytes (~97.88 MiB / 102.6 MB)
- **Total Rows (Observations):** 284,807 transactions
- **Total Columns (Features):** 31 columns
- **Missing / Null Values:** 0 (clean dataset with zero missing cells)

### Target & Label Column
- **Column Name:** `Class`
- **Data Type:** Integer / binary category (`0` or `1`)
- **Semantics:**
  - `0`: Legitimate transaction
  - `1`: Fraudulent transaction

### Fraud vs. Legitimate Distribution & Ratio
| Class | Label | Count | Percentage |
| :--- | :--- | :--- | :--- |
| `0` | Legitimate | 284,315 | 99.8273% |
| `1` | Fraudulent | 492 | 0.1727% |
| **Total** | | **284,807** | **100.0000%** |

- **Class Imbalance Ratio:** ~577.88 : 1 (1 fraud per ~578 legitimate transactions).
- **Domain Fit:** Reflects real European cardholder credit card transactions over a two-day observation window (September 2013), matching Sentinel V1's card-not-present (CNP), outgoing pre-authorization payment rail domain.

### Feature Schema Summary
- **`Time`** (float): Seconds elapsed between each transaction and the first transaction in the dataset (range: 0 to 172,792 seconds, ~48 hours).
- **`V1` – `V28`** (float): 28 principal component numerical features obtained via PCA for confidentiality.
- **`Amount`** (float): Transaction monetary value (mean: $88.35, median: $22.00, std: $250.12, min: $0.00, max: $25,691.16).
- **`Class`** (int): Ground-truth fraud label (`0` or `1`).

---

## 2. Directory Structure & Data Policy
```
data/
├── README.md               # Dataset documentation & provenance (this file)
├── raw/                    # Raw external datasets (ignored by Git, except documentation)
│   ├── README.md           # Raw directory notes
│   └── creditcard.csv      # Downloaded raw CSV (102.6 MB, .gitignored)
├── processed/              # Cleaned splits (train / evaluation splits, .gitignored)
├── scenarios/              # JSON scenarios (flagship demo & test scenarios)
└── seed/                   # Deterministic fixture seed data (customers, cards, merchants)
```

- **Git Exclusion Policy:** Raw data files (`*.csv`, `*.arff`, `*.parquet`) in `data/raw/` and derived training splits in `data/processed/` are excluded via `.gitignore` to prevent repository bloat.

---

## 3. Train / Held-Out Split (80/20 Stratified)

Per the Sentinel V1 Build Checklist, the raw dataset is partitioned into an 80% training split and a 20% held-out evaluation split.

- **Split Script:** `scripts/split_dataset.py`
- **Random Seed:** `42` (`sklearn.model_selection.train_test_split`, `shuffle=True`)
- **Stratification:** Stratified on `Class` to preserve exact fraud proportion across partitions.
- **Held-Out Isolation:** The held-out split is reserved exclusively for baseline evaluation and must **never** be accessed during model fitting or fixture generation.

### Split Partition Metrics
| Partition | File Path | Total Rows | Legit (`0`) | Fraud (`1`) | Fraud Ratio | Share |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Train Set** | `data/processed/train.csv` | 227,845 | 227,451 | 394 | 0.1729% | 80.00% |
| **Held-Out Set** | `data/processed/held_out.csv` | 56,962 | 56,864 | 98 | 0.1720% | 20.00% |
| **Full Raw** | `data/raw/creditcard.csv` | 284,807 | 284,315 | 492 | 0.1727% | 100.00% |

- **Leakage Check:** 0 overlapping indices between train and held-out (`train_indices ∩ held_out_indices = ∅`).
- **Raw Data Check:** Raw dataset SHA-256 hash verified unchanged before and after splitting (`33a178be65174943a07d1736acf5898f6c8e1fa80950dbbe598c17eda968ec59`).

---

## 4. Feature Normalization & Transaction Representation

Per Phase 1.1 of the Sentinel V1 Build Checklist, raw credit card columns are cleaned, imputed, and normalized via `scripts/preprocess.py` into a standardized 33-feature numeric matrix compatible with Sentinel risk models:

### Feature Mapping Table
| Source Column | Sentinel Feature | Transformation / Meaning | Training Parameter Baseline |
| :--- | :--- | :--- | :--- |
| **`Amount`** | `amount_scaled` | Z-score standardization: `(Amount - mean) / std` | $\mu = 88.1763$, $\sigma = 250.7226$ |
| **`Amount`** | `amount_log1p` | Natural log: $\ln(1 + \max(0, \text{Amount}))$ | Compresses heavy monetary tail |
| **`Time`** | `hour_of_day` | Cyclical hour: `(Time // 3600) % 24` | Diurnal cycle `[0..23]` |
| **`Time`** | `time_sin` | Continuous sine: $\sin(2\pi \cdot \text{hour} / 24)$ | Cyclical diurnal continuity |
| **`Time`** | `time_cos` | Continuous cosine: $\cos(2\pi \cdot \text{hour} / 24)$ | Cyclical diurnal continuity |
| **`V1` – `V28`** | `V1` – `V28` | 28 latent PCA behavioral/terminal components | Missing values imputed via train medians |
| **`Class`** | Target vector $y$ | Stripped from feature matrix $X$; preserved separately | Binary integer: `0` (legit) vs `1` (fraud) |

- **Strict Training Isolation:** Preprocessing statistics were fitted **exclusively on `train.csv`** and serialized to `data/processed/preprocessor_params.json`.
- **Zero-Leakage Replay:** Held-out data (`held_out.csv`) was never inspected during fitting and is transformed strictly via inference with frozen parameters.
- **Transaction Domain Bridge:** `TransactionFeaturePreprocessor.transform_transaction(tx)` allows mapping live Sentinel `Transaction` domain entities into this feature space.


