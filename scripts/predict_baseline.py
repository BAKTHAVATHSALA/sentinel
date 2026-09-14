"""Single-transaction inference wrapper for the Sentinel detection baseline model.

Phase 1.2 of the Sentinel V1 Build Checklist requires the trained baseline model
(models/sentinel_baseline_model.joblib, produced by scripts/train_baseline.py and
evaluated in scripts/evaluate_baseline.py) to be wrapped behind a simple
predict(transaction) -> risk_score function, with risk_band derived from the
held-out score distribution (eval/risk_thresholds.json / scripts/derive_thresholds.py).

Guarantees:
- Zero retraining, refitting, or hyperparameter tuning; loads the existing frozen
  model artifact and frozen preprocessor parameters only.
- V1-V28 are anonymized PCA components from the source benchmark dataset with no
  live Sentinel Transaction equivalent (no real CNP transaction carries them). When
  not explicitly supplied they are imputed with the frozen training medians, exactly
  as scripts/preprocess.py does for held-out evaluation. This mirrors a real
  production constraint of adopting a public benchmark dataset, not a shortcut.
- risk_band thresholds are the same LOW/HIGH cutoffs already derived from the
  held-out score distribution in scripts/derive_thresholds.py -- never re-guessed here.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Dict

import joblib
from sklearn.linear_model import LogisticRegression

from scripts.derive_thresholds import HIGH_THRESHOLD, LOW_THRESHOLD
from scripts.preprocess import DEFAULT_PROCESSED_DIR, TransactionFeaturePreprocessor
from shared.contracts.detection import RiskBand
from shared.contracts.transaction import Transaction

DEFAULT_MODEL_PATH = Path("models/sentinel_baseline_model.joblib")
DEFAULT_PARAMS_PATH = DEFAULT_PROCESSED_DIR / "preprocessor_params.json"


def risk_band_for_score(risk_score: Decimal) -> RiskBand:
    """Map a risk_score to LOW/MEDIUM/HIGH using the held-out-derived thresholds.

    :param risk_score: Model-produced fraud probability in [0, 1].
    :return: RiskBand per eval/risk_thresholds.json mapping rules.
    """
    high_cutoff = Decimal(str(HIGH_THRESHOLD))
    low_cutoff = Decimal(str(LOW_THRESHOLD))

    if risk_score >= high_cutoff:
        return RiskBand.HIGH
    if risk_score >= low_cutoff:
        return RiskBand.MEDIUM
    return RiskBand.LOW


def predict(
    transaction: Transaction,
    latent_pca: Dict[str, float] | None = None,
    model_path: Path = DEFAULT_MODEL_PATH,
    params_path: Path = DEFAULT_PARAMS_PATH,
) -> Decimal:
    """Score a single transaction with the trained detection baseline model.

    :param transaction: Candidate Sentinel Transaction to score.
    :param latent_pca: Optional known V1..V28 values; imputed with frozen training
        medians when omitted (see module docstring).
    :param model_path: Path to the trained model artifact.
    :param params_path: Path to the frozen preprocessor parameters.
    :return: risk_score as a Decimal in [0, 1], quantized to 4 decimal places.
    """
    if not model_path.exists():
        raise FileNotFoundError(
            f"[predict_baseline] - Model artifact missing at {model_path}. "
            "Run scripts/train_baseline.py first."
        )
    if not params_path.exists():
        raise FileNotFoundError(
            f"[predict_baseline] - Preprocessor parameters missing at {params_path}. "
            "Run scripts/preprocess.py first."
        )

    model: LogisticRegression = joblib.load(model_path)
    preprocessor = TransactionFeaturePreprocessor.load_parameters(params_path)

    X = preprocessor.transform_transaction(transaction, latent_pca=latent_pca)
    fraud_probability = float(model.predict_proba(X)[0, 1])

    return Decimal(str(round(fraud_probability, 4))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def predict_with_band(
    transaction: Transaction,
    latent_pca: Dict[str, float] | None = None,
    model_path: Path = DEFAULT_MODEL_PATH,
    params_path: Path = DEFAULT_PARAMS_PATH,
) -> tuple[Decimal, RiskBand]:
    """Score a transaction and resolve its risk_band in one call.

    :param transaction: Candidate Sentinel Transaction to score.
    :param latent_pca: Optional known V1..V28 values; imputed otherwise.
    :param model_path: Path to the trained model artifact.
    :param params_path: Path to the frozen preprocessor parameters.
    :return: Tuple of (risk_score, risk_band).
    """
    risk_score = predict(
        transaction, latent_pca=latent_pca, model_path=model_path, params_path=params_path
    )
    return risk_score, risk_band_for_score(risk_score)
