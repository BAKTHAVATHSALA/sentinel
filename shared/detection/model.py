"""Deterministic machine learning risk scoring model for Sentinel V1 detection."""

from decimal import Decimal, ROUND_HALF_UP
import numpy as np
from sklearn.linear_model import LogisticRegression

from shared.contracts.detection import AnomalyTag, RiskBand
from shared.contracts.transaction import Transaction
from shared.generator.models import CustomerProfile, MerchantProfile

MODEL_NAME = "sentinel-deterministic-risk-scorer"
MODEL_VERSION = "v1.0.0"

# Risk band threshold cutoffs
LOW_RISK_THRESHOLD = Decimal("0.40")
HIGH_RISK_THRESHOLD = Decimal("0.75")


def extract_feature_vector(
    transaction: Transaction,
    anomaly_tags: list[AnomalyTag],
    customer: CustomerProfile | None = None,
    merchant: MerchantProfile | None = None,
) -> list[float]:
    """Extract numerical feature vector for the risk model.

    Features:
    0: Normalized transaction amount
    1: Total anomaly tag count
    2: Is NEW_DEVICE present
    3: Is UNUSUAL_LOCATION present
    4: Is UNUSUAL_AMOUNT present
    5: Is UNUSUAL_TIME present
    6: Is IMPOSSIBLE_TRAVEL present
    7: Is MERCHANT_RISK present
    8: Is LINKED_ENTITY_ANOMALY present
    9: Is KYC_ANOMALY present
    10: Merchant chargeback rate
    """
    tag_set = set(anomaly_tags)
    amount_scaled = float(transaction.amount) / 500.0  # normalized around $500 baseline

    cb_rate = float(merchant.chargeback_rate) if merchant else 0.005

    return [
        amount_scaled,
        float(len(anomaly_tags)),
        1.0 if AnomalyTag.NEW_DEVICE in tag_set else 0.0,
        1.0 if AnomalyTag.UNUSUAL_LOCATION in tag_set else 0.0,
        1.0 if AnomalyTag.UNUSUAL_AMOUNT in tag_set else 0.0,
        1.0 if AnomalyTag.UNUSUAL_TIME in tag_set else 0.0,
        1.0 if AnomalyTag.IMPOSSIBLE_TRAVEL in tag_set else 0.0,
        1.0 if AnomalyTag.MERCHANT_RISK in tag_set else 0.0,
        1.0 if AnomalyTag.LINKED_ENTITY_ANOMALY in tag_set else 0.0,
        1.0 if AnomalyTag.KYC_ANOMALY in tag_set else 0.0,
        cb_rate * 100.0,
    ]


def build_and_fit_model(random_state: int = 42) -> LogisticRegression:
    """Train a reproducible deterministic LogisticRegression model on synthetic training distributions."""
    rng = np.random.RandomState(random_state)
    X_samples: list[list[float]] = []
    y_samples: list[int] = []

    # 1. Normal baseline samples (low risk, label 0)
    for _ in range(80):
        amount_scaled = rng.uniform(0.05, 0.4)
        X_samples.append([amount_scaled, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5])
        y_samples.append(0)

    # 2. Single-signal anomaly samples (medium risk, label 1)
    for _ in range(40):
        amount_scaled = rng.uniform(0.2, 0.8)
        tag_idx = rng.randint(2, 10)
        vec = [amount_scaled, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.5]
        vec[tag_idx] = 1.0
        X_samples.append(vec)
        y_samples.append(1)

    # 3. Multi-signal high risk samples (e.g. 2+ tags, label 1)
    for _ in range(60):
        amount_scaled = rng.uniform(0.6, 2.0)
        vec = [amount_scaled, 3.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 3.5]
        X_samples.append(vec)
        y_samples.append(1)

    clf = LogisticRegression(random_state=random_state, max_iter=200, C=1.0)
    clf.fit(np.array(X_samples), np.array(y_samples))
    return clf


class RiskScoringModel:
    """Deterministic, seedable risk scoring engine using a fitted scikit-learn model."""

    def __init__(self, random_state: int = 42) -> None:
        """Initialize and fit the deterministic risk model."""
        self.random_state = random_state
        self.model_name = MODEL_NAME
        self.model_version = MODEL_VERSION
        self._classifier = build_and_fit_model(random_state=random_state)

    def score(
        self,
        transaction: Transaction,
        anomaly_tags: list[AnomalyTag],
        customer: CustomerProfile | None = None,
        merchant: MerchantProfile | None = None,
    ) -> tuple[Decimal, RiskBand]:
        """Compute the risk score and risk band for a transaction.

        :param transaction: Candidate transaction.
        :param anomaly_tags: Identified anomaly tags.
        :param customer: Customer profile.
        :param merchant: Merchant profile.
        :return: Tuple of (risk_score, risk_band).
        """
        features = extract_feature_vector(transaction, anomaly_tags, customer, merchant)
        prob = float(self._classifier.predict_proba(np.array([features]))[0, 1])

        # Bound score between 0.05 and 0.95 and quantize to 2 decimal places
        bounded = max(0.05, min(0.95, prob))
        risk_score = Decimal(str(round(bounded, 2))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if risk_score >= HIGH_RISK_THRESHOLD:
            band = RiskBand.HIGH
        elif risk_score >= LOW_RISK_THRESHOLD:
            band = RiskBand.MEDIUM
        else:
            band = RiskBand.LOW

        return risk_score, band
