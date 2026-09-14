"""Unit tests for the single-transaction detection baseline predict() wrapper."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from scripts.derive_thresholds import HIGH_THRESHOLD, LOW_THRESHOLD
from scripts.predict_baseline import DEFAULT_MODEL_PATH, DEFAULT_PARAMS_PATH, predict, predict_with_band, risk_band_for_score
from shared.contracts.detection import RiskBand
from shared.contracts.transaction import (
    AuthorizationStage,
    Channel,
    Direction,
    Geo,
    PaymentRail,
    Transaction,
)


def _make_transaction(amount: str = "150.50", hour: int = 14) -> Transaction:
    return Transaction(
        transaction_id="tx_predict_test_001",
        customer_id="cust_001",
        account_id="acc_001",
        card_id="card_001",
        merchant_id="merch_001",
        amount=Decimal(amount),
        currency="USD",
        timestamp=datetime(2026, 9, 14, hour, 0, tzinfo=timezone.utc),
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_001",
        ip_address="192.168.1.1",
        geo=Geo(lat=Decimal("37.7749"), lon=Decimal("-122.4194"), country="US"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )


def _artifacts_available() -> bool:
    return DEFAULT_MODEL_PATH.exists() and DEFAULT_PARAMS_PATH.exists()


def test_predict_missing_model_artifact_raises(tmp_path) -> None:
    """predict() must fail loudly, never silently, when the model artifact is absent."""
    tx = _make_transaction()
    bogus_model_path = tmp_path / "does_not_exist.joblib"

    with pytest.raises(FileNotFoundError, match="Model artifact missing"):
        predict(tx, model_path=bogus_model_path)


def test_predict_returns_bounded_decimal_probability() -> None:
    """predict() must return a Decimal risk_score strictly within [0, 1]."""
    if not _artifacts_available():
        pytest.skip("Trained model artifact or preprocessor parameters not present.")

    tx = _make_transaction()
    risk_score = predict(tx)

    assert isinstance(risk_score, Decimal)
    assert Decimal("0.0000") <= risk_score <= Decimal("1.0000")


def test_predict_is_deterministic() -> None:
    """Same transaction and same latent_pca must always produce the identical risk_score."""
    if not _artifacts_available():
        pytest.skip("Trained model artifact or preprocessor parameters not present.")

    tx = _make_transaction()
    latent_pca = {"V1": 1.25, "V2": -0.75, "V14": -3.5}

    score1 = predict(tx, latent_pca=latent_pca)
    score2 = predict(tx, latent_pca=latent_pca)

    assert score1 == score2


def test_predict_missing_latent_pca_uses_training_medians() -> None:
    """Omitting latent_pca must impute V1..V28 with the same frozen training medians
    used during held-out evaluation, matching TransactionFeaturePreprocessor's own guarantee."""
    if not _artifacts_available():
        pytest.skip("Trained model artifact or preprocessor parameters not present.")

    tx = _make_transaction()

    score_omitted = predict(tx, latent_pca=None)
    score_empty = predict(tx, latent_pca={})

    assert score_omitted == score_empty


def test_predict_with_band_matches_risk_band_for_score() -> None:
    """predict_with_band() must return a band consistent with risk_band_for_score(risk_score)."""
    if not _artifacts_available():
        pytest.skip("Trained model artifact or preprocessor parameters not present.")

    tx = _make_transaction()
    risk_score, band = predict_with_band(tx)

    assert band == risk_band_for_score(risk_score)


def test_risk_band_for_score_boundaries() -> None:
    """risk_band_for_score() must apply the exact held-out-derived LOW/HIGH cutoffs at their boundaries."""
    low_cutoff = Decimal(str(LOW_THRESHOLD))
    high_cutoff = Decimal(str(HIGH_THRESHOLD))

    assert risk_band_for_score(low_cutoff - Decimal("0.0001")) == RiskBand.LOW
    assert risk_band_for_score(low_cutoff) == RiskBand.MEDIUM
    assert risk_band_for_score(high_cutoff - Decimal("0.0001")) == RiskBand.MEDIUM
    assert risk_band_for_score(high_cutoff) == RiskBand.HIGH
    assert risk_band_for_score(Decimal("0.0000")) == RiskBand.LOW
    assert risk_band_for_score(Decimal("1.0000")) == RiskBand.HIGH
