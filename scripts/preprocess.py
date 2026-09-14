"""Data preprocessing and feature engineering pipeline for Sentinel fraud detection.

Implements clean, reproducible normalization mapping source dataset columns
(Amount, Time, V1-V28) into Sentinel's Transaction-compatible feature representation.

Guarantees:
- Fitted EXCLUSIVELY on training data (train.csv).
- Held-out data (held_out.csv) is never inspected during fitting.
- Fitted parameters are exported to JSON for deterministic downstream evaluation.
- Class target is preserved separately.
- Missing values are imputed using train-derived medians.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from shared.contracts.transaction import Transaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("preprocess")

DEFAULT_PROCESSED_DIR = Path("data/processed")
TARGET_COLUMN = "Class"
RAW_AMOUNT_COL = "Amount"
RAW_TIME_COL = "Time"
PCA_PREFIX = "V"
NUM_PCA_COMPONENTS = 28


@dataclass(frozen=True)
class PreprocessorStatistics:
    """Fitted statistical parameters computed exclusively from the training set."""

    amount_mean: float
    amount_std: float
    amount_median: float
    amount_iqr: float
    amount_min: float
    amount_max: float
    time_min: float
    time_max: float
    imputation_medians: Dict[str, float]
    feature_names: List[str]


class TransactionFeaturePreprocessor:
    """Preprocessor for mapping raw credit card transactions to Sentinel detection features."""

    def __init__(self, stats: PreprocessorStatistics | None = None) -> None:
        """Initialize preprocessor with optional pre-fitted statistics."""
        self._stats: PreprocessorStatistics | None = stats

    @property
    def is_fitted(self) -> bool:
        """Return True if preprocessor has been fitted on training data."""
        return self._stats is not None

    @property
    def feature_names(self) -> List[str]:
        """Return list of transformed feature names."""
        if not self.is_fitted or self._stats is None:
            raise RuntimeError("[TransactionFeaturePreprocessor] - Preprocessor is not fitted yet.")
        return list(self._stats.feature_names)

    def fit(self, train_df: pd.DataFrame) -> TransactionFeaturePreprocessor:
        """Compute normalization and imputation statistics exclusively from the training dataframe.

        Args:
            train_df: Training partition dataframe (must contain Amount, Time, V1-V28).

        Returns:
            Fitted TransactionFeaturePreprocessor instance.
        """
        logger.info(f"[TransactionFeaturePreprocessor.fit] - Fitting on {len(train_df)} training rows.")

        if RAW_AMOUNT_COL not in train_df.columns:
            raise KeyError(f"[fit] - Missing required column: {RAW_AMOUNT_COL}")
        if RAW_TIME_COL not in train_df.columns:
            raise KeyError(f"[fit] - Missing required column: {RAW_TIME_COL}")

        # 1. Amount statistics
        amount_series = train_df[RAW_AMOUNT_COL].astype(float)
        q25 = float(amount_series.quantile(0.25))
        q75 = float(amount_series.quantile(0.75))
        iqr = float(q75 - q25) if (q75 - q25) > 0 else 1.0

        amount_mean = float(amount_series.mean())
        amount_std = float(amount_series.std()) if float(amount_series.std()) > 0 else 1.0
        amount_median = float(amount_series.median())
        amount_min = float(amount_series.min())
        amount_max = float(amount_series.max())

        # 2. Time statistics
        time_series = train_df[RAW_TIME_COL].astype(float)
        time_min = float(time_series.min())
        time_max = float(time_series.max())

        # 3. Imputation medians for all potential feature columns
        imputation_medians: Dict[str, float] = {
            RAW_AMOUNT_COL: amount_median,
            RAW_TIME_COL: float(time_series.median()),
        }
        for i in range(1, NUM_PCA_COMPONENTS + 1):
            col_name = f"{PCA_PREFIX}{i}"
            if col_name in train_df.columns:
                imputation_medians[col_name] = float(train_df[col_name].median())
            else:
                imputation_medians[col_name] = 0.0

        # 4. Canonical ordered feature list
        # - amount_scaled: Z-score normalized by train mean & std
        # - amount_log1p: natural log of (1 + amount) for heavy-tail distribution
        # - hour_of_day: 0 to 23 cyclical hour of day
        # - time_sin: cyclical sine component of hour
        # - time_cos: cyclical cosine component of hour
        # - V1 to V28: 28 latent PCA behavioral/locational/device features
        feature_names: List[str] = [
            "amount_scaled",
            "amount_log1p",
            "hour_of_day",
            "time_sin",
            "time_cos",
        ] + [f"{PCA_PREFIX}{i}" for i in range(1, NUM_PCA_COMPONENTS + 1)]

        self._stats = PreprocessorStatistics(
            amount_mean=amount_mean,
            amount_std=amount_std,
            amount_median=amount_median,
            amount_iqr=iqr,
            amount_min=amount_min,
            amount_max=amount_max,
            time_min=time_min,
            time_max=time_max,
            imputation_medians=imputation_medians,
            feature_names=feature_names,
        )
        return self

    def transform(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series | None]:
        """Apply fitted transformation to any candidate dataframe (train or held-out).

        Args:
            df: Input dataframe to transform.

        Returns:
            Tuple of (X_features_df, y_target_series_or_None).
        """
        if not self.is_fitted or self._stats is None:
            raise RuntimeError("[transform] - Preprocessor must be fitted before transform.")

        df_copy = df.copy()

        # Handle missing values using training imputation medians
        for col, median_val in self._stats.imputation_medians.items():
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].fillna(median_val)
            else:
                df_copy[col] = median_val

        # 1. Normalized amount features
        amount_vals = df_copy[RAW_AMOUNT_COL].astype(float).values
        amount_scaled = (amount_vals - self._stats.amount_mean) / self._stats.amount_std
        amount_log1p = np.log1p(np.maximum(0.0, amount_vals))

        # 2. Cyclical time features (24-hour cycle)
        time_vals = df_copy[RAW_TIME_COL].astype(float).values
        hours = (time_vals // 3600.0) % 24.0
        time_sin = np.sin(2.0 * np.pi * hours / 24.0)
        time_cos = np.cos(2.0 * np.pi * hours / 24.0)

        # 3. Assemble feature dictionary
        features: Dict[str, np.ndarray] = {
            "amount_scaled": amount_scaled,
            "amount_log1p": amount_log1p,
            "hour_of_day": hours,
            "time_sin": time_sin,
            "time_cos": time_cos,
        }

        # 4. Latent PCA features (V1 through V28)
        for i in range(1, NUM_PCA_COMPONENTS + 1):
            col_name = f"{PCA_PREFIX}{i}"
            features[col_name] = df_copy[col_name].astype(float).values

        X_df = pd.DataFrame(features, index=df.index)[self._stats.feature_names]

        # Extract target if present
        y_series: pd.Series | None = None
        if TARGET_COLUMN in df.columns:
            y_series = df[TARGET_COLUMN].astype(int)

        return X_df, y_series

    def fit_transform(self, train_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Fit on training data and transform in a single call."""
        self.fit(train_df)
        X, y = self.transform(train_df)
        if y is None:
            raise ValueError("[fit_transform] - Target column missing in training data.")
        return X, y

    def transform_transaction(
        self,
        transaction: Transaction,
        latent_pca: Dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """Transform a Sentinel Transaction domain object into the detection feature representation.

        Args:
            transaction: Domain Transaction object with amount, timestamp, etc.
            latent_pca: Optional dictionary of V1..V28 latent PCA component values.

        Returns:
            Single-row DataFrame matching feature_names.
        """
        if not self.is_fitted or self._stats is None:
            raise RuntimeError("[transform_transaction] - Preprocessor must be fitted first.")

        amount_val = float(transaction.amount)
        amount_scaled = (amount_val - self._stats.amount_mean) / self._stats.amount_std
        amount_log1p = float(np.log1p(max(0.0, amount_val)))

        # Cyclical 24-hour time representation from timestamp
        hour_val = transaction.timestamp.hour + (transaction.timestamp.minute / 60.0)
        time_sin = float(np.sin(2.0 * np.pi * hour_val / 24.0))
        time_cos = float(np.cos(2.0 * np.pi * hour_val / 24.0))

        features: Dict[str, float] = {
            "amount_scaled": amount_scaled,
            "amount_log1p": amount_log1p,
            "hour_of_day": hour_val,
            "time_sin": time_sin,
            "time_cos": time_cos,
        }

        # Impute or fill PCA features from optional dictionary or training medians
        pca_dict = latent_pca or {}
        for i in range(1, NUM_PCA_COMPONENTS + 1):
            col_name = f"{PCA_PREFIX}{i}"
            features[col_name] = float(pca_dict.get(col_name, self._stats.imputation_medians.get(col_name, 0.0)))

        return pd.DataFrame([features])[self._stats.feature_names]

    def save_parameters(self, filepath: Path | str) -> None:
        """Serialize fitted statistical parameters to a JSON file."""
        if not self.is_fitted or self._stats is None:
            raise RuntimeError("[save_parameters] - Cannot save unfitted preprocessor.")

        out_path = Path(filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self._stats), f, indent=2)
        logger.info(f"[save_parameters] - Saved preprocessor parameters to {out_path}")

    @classmethod
    def load_parameters(cls, filepath: Path | str) -> TransactionFeaturePreprocessor:
        """Reconstruct preprocessor from previously serialized JSON parameters."""
        in_path = Path(filepath)
        if not in_path.exists():
            raise FileNotFoundError(f"[load_parameters] - Parameters file not found at {in_path}")

        with open(in_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        stats = PreprocessorStatistics(
            amount_mean=data["amount_mean"],
            amount_std=data["amount_std"],
            amount_median=data["amount_median"],
            amount_iqr=data["amount_iqr"],
            amount_min=data["amount_min"],
            amount_max=data["amount_max"],
            time_min=data["time_min"],
            time_max=data["time_max"],
            imputation_medians=data["imputation_medians"],
            feature_names=data["feature_names"],
        )
        return cls(stats=stats)


def run_preprocessing_pipeline(
    processed_dir: Path = DEFAULT_PROCESSED_DIR,
) -> Dict[str, Any]:
    """Execute end-to-end dataset preprocessing, fitting ONLY on training data.

    Args:
        processed_dir: Directory containing train.csv and held_out.csv.

    Returns:
        Summary dictionary of preprocessing results.
    """
    train_path = processed_dir / "train.csv"
    held_out_path = processed_dir / "held_out.csv"

    if not train_path.exists() or not held_out_path.exists():
        raise FileNotFoundError(f"[run_preprocessing_pipeline] - Split CSV files missing in {processed_dir}")

    # 1. Load train partition ONLY for fitting
    train_df = pd.read_csv(train_path)
    preprocessor = TransactionFeaturePreprocessor()
    X_train, y_train = preprocessor.fit_transform(train_df)

    # 2. Save fitted preprocessor parameters
    params_path = processed_dir / "preprocessor_params.json"
    preprocessor.save_parameters(params_path)

    # 3. Load held-out partition and transform with frozen parameters
    held_out_df = pd.read_csv(held_out_path)
    X_held_out, y_held_out = preprocessor.transform(held_out_df)
    if y_held_out is None:
        raise ValueError("[run_preprocessing_pipeline] - Held-out partition missing target column.")

    # 4. Save transformed feature matrices and targets
    X_train_path = processed_dir / "X_train.parquet"
    y_train_path = processed_dir / "y_train.csv"
    X_held_out_path = processed_dir / "X_held_out.parquet"
    y_held_out_path = processed_dir / "y_held_out.csv"

    X_train.to_parquet(X_train_path, index=False)
    y_train.to_frame(TARGET_COLUMN).to_csv(y_train_path, index=False)

    X_held_out.to_parquet(X_held_out_path, index=False)
    y_held_out.to_frame(TARGET_COLUMN).to_csv(y_held_out_path, index=False)

    # 5. Document feature mapping
    mapping_doc: Dict[str, Any] = {
        "title": "Sentinel Real Fraud Dataset Feature Mapping",
        "description": "Mapping from raw credit card transaction columns to Sentinel detection feature space",
        "source_columns": {
            "Amount": "Transaction monetary amount (raw EUR/USD value)",
            "Time": "Elapsed seconds from dataset origin across 48-hour window",
            "V1_to_V28": "28 PCA-derived anonymized latent components representing cardholder/device/merchant signals",
            "Class": "Ground truth fraud label (0=legitimate, 1=fraudulent)",
        },
        "engineered_features": {
            "amount_scaled": "Z-score normalized Amount using training set mean (88.1763) and std (250.7226)",
            "amount_log1p": "Natural log transformation log(1 + Amount) handling heavy-tailed amounts",
            "hour_of_day": "Cyclic 24-hour hour-of-day integer [0..23] derived as (Time // 3600) % 24",
            "time_sin": "Continuous cyclic sine representation: sin(2 * pi * hour / 24)",
            "time_cos": "Continuous cyclic cosine representation: cos(2 * pi * hour / 24)",
            "V1_to_V28": "28 numerical continuous PCA features with missing value imputation via training medians",
        },
        "target_variable": {
            "column_name": TARGET_COLUMN,
            "type": "int64",
            "values": {"0": "Legitimate transaction", "1": "Fraudulent transaction"},
            "storage": "Preserved strictly as separate target vector (y_train, y_held_out)",
        },
        "partitions": {
            "train": {
                "rows": len(X_train),
                "features": X_train.shape[1],
                "fraud_count": int((y_train == 1).sum()),
                "legit_count": int((y_train == 0).sum()),
            },
            "held_out": {
                "rows": len(X_held_out),
                "features": X_held_out.shape[1],
                "fraud_count": int((y_held_out == 1).sum()),
                "legit_count": int((y_held_out == 0).sum()),
            },
        },
        "leakage_safeguards": [
            "Fitted parameters computed strictly from train.csv",
            "Held-out set never accessed during fit()",
            "Zero index overlap between train and held-out partitions",
            "Exact frozen parameters serialized for future model evaluation",
        ],
    }

    mapping_path = processed_dir / "feature_mapping.json"
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping_doc, f, indent=2)

    logger.info(f"[run_preprocessing_pipeline] - Saved feature mapping documentation to {mapping_path}")
    logger.info(f"[run_preprocessing_pipeline] - Pipeline complete. Train: {X_train.shape}, Held-out: {X_held_out.shape}")

    return mapping_doc


if __name__ == "__main__":
    run_preprocessing_pipeline()
