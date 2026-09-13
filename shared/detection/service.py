"""Detection service orchestrating anomaly tagging and risk scoring for Sentinel V1."""

from datetime import datetime, timezone

from shared.contracts.detection import DetectionOutput
from shared.contracts.transaction import Transaction
from shared.detection.model import RiskScoringModel
from shared.detection.rules import evaluate_all_anomalies
from shared.generator.models import CustomerProfile, MerchantProfile, ScenarioResult


class DetectionService:
    """Service orchestrating deterministic anomaly tagging and ML risk scoring."""

    def __init__(self, random_state: int = 42) -> None:
        """Initialize the detection service with a fitted deterministic model."""
        self._model = RiskScoringModel(random_state=random_state)

    def detect(
        self,
        transaction: Transaction,
        customer: CustomerProfile | None = None,
        history: list[Transaction] | None = None,
        merchant: MerchantProfile | None = None,
        secondary_customer: CustomerProfile | None = None,
        case_id: str | None = None,
    ) -> DetectionOutput:
        """Evaluate a transaction, producing the frozen DetectionOutput contract.

        :param transaction: The candidate Transaction to evaluate.
        :param customer: Baseline profile for the customer.
        :param history: Prior transactions for customer/device.
        :param merchant: Profile of the transaction merchant.
        :param secondary_customer: Linked entity profile, if any.
        :param case_id: Optional case identifier; defaults to generated ID.
        :return: DetectionOutput contract.
        """
        cid = case_id or f"case_{transaction.transaction_id}"

        # 1. Deterministic anomaly tagging
        tags, reasons = evaluate_all_anomalies(
            transaction=transaction,
            customer=customer,
            history=history,
            merchant=merchant,
            secondary_customer=secondary_customer,
        )

        if not reasons:
            reasons = ["Baseline normal behavior; no anomaly rules triggered"]

        # 2. Model risk scoring
        risk_score, risk_band = self._model.score(
            transaction=transaction,
            anomaly_tags=tags,
            customer=customer,
            merchant=merchant,
        )

        # 3. Construct and validate DetectionOutput
        return DetectionOutput(
            case_id=cid,
            transaction_id=transaction.transaction_id,
            risk_score=risk_score,
            risk_band=risk_band,
            anomaly_tags=tags,
            detection_reasons=reasons,
            model_name=self._model.model_name,
            model_version=self._model.model_version,
            detected_at=datetime.now(timezone.utc),
        )

    def detect_scenario(
        self,
        scenario: ScenarioResult,
        case_id: str | None = None,
    ) -> DetectionOutput:
        """Evaluate a generated scenario container directly.

        :param scenario: The ScenarioResult produced by synthetic generator.
        :param case_id: Optional case identifier.
        :return: DetectionOutput contract.
        """
        return self.detect(
            transaction=scenario.target_transaction,
            customer=scenario.customer_profile,
            history=scenario.baseline_transactions,
            merchant=scenario.merchant_profile,
            secondary_customer=scenario.secondary_profile,
            case_id=case_id,
        )
