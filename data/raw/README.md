# Raw Data: Credit Card Fraud Detection Dataset

### Dataset Metadata
- **Dataset Name:** Credit Card Fraud Detection (Kaggle / ULB Machine Learning Group)
- **Primary Source:** [Kaggle - Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
- **OpenML Reference:** [OpenML Dataset 42175](https://www.openml.org/d/42175)
- **Direct Mirror URL:** `https://raw.githubusercontent.com/nsethi31/Kaggle-Data-Credit-Card-Fraud-Detection/master/creditcard.csv`
- **Download/Access Date:** 2026-09-14
- **License / Usage Terms:** Open Data Commons Public Domain Dedication and License (PDDL) v1.0 / Database Contents License (DbCL) v1.0 (Public domain dedication by ULB ML Group / Worldline)
- **Raw Filename:** `creditcard.csv`
- **File Size:** 102,634,230 bytes (~102.6 MB)
- **Dimensions:** 284,807 rows × 31 columns
- **Target Label Column:** `Class` (binary: `0` = Legitimate transaction, `1` = Fraudulent transaction)
- **Class Distribution:**
  - Legitimate (`0`): 284,315 transactions (99.8273%)
  - Fraudulent (`1`): 492 transactions (0.1727%)
- **Feature Overview:**
  - `Time`: Elapsed seconds from the first transaction in the dataset over 2 days (September 2013).
  - `V1` through `V28`: Principal components obtained via PCA transformation (numerical).
  - `Amount`: Transaction monetary amount.
  - `Class`: Response variable (0 = Normal, 1 = Fraud).

### Storage Guidelines
- Raw data files in this directory (`*.csv`, `*.arff`, `*.parquet`) are excluded from Git version control via `.gitignore`.
- Derived and preprocessed training/evaluation splits will reside in `data/processed/`.
- Comprehensive project data documentation is maintained in [`data/README.md`](../README.md).
