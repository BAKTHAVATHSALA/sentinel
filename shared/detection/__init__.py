"""Fraud detection and deterministic anomaly tagging package for Sentinel V1."""

from shared.contracts.detection import DetectionOutput
from shared.contracts.transaction import Transaction
from shared.detection.model import (
    HIGH_RISK_THRESHOLD,
    LOW_RISK_THRESHOLD,
    MODEL_NAME,
    MODEL_VERSION,
    RiskScoringModel,
)
from shared.detection.rules import (
    LOCATION_DEVIATION_THRESHOLD_KM,
    MERCHANT_CHARGEBACK_THRESHOLD,
    UNUSUAL_AMOUNT_ABSOLUTE_THRESHOLD,
    calculate_haversine_distance_km,
    evaluate_all_anomalies,
)
from shared.detection.service import DetectionService
from shared.generator.models import CustomerProfile, MerchantProfile, ScenarioResult

# Module-level default singleton service
_default_service = DetectionService(random_state=42)


def detect_transaction(
    transaction: Transaction,
    customer: CustomerProfile | None = None,
    history: list[Transaction] | None = None,
    merchant: MerchantProfile | None = None,
    secondary_customer: CustomerProfile | None = None,
    case_id: str | None = None,
) -> DetectionOutput:
    """Evaluate a single transaction with optional customer and history baselines.

    :param transaction: The candidate transaction.
    :param customer: Customer profile baseline.
    :param history: Prior transactions.
    :param merchant: Merchant profile.
    :param secondary_customer: Linked customer profile.
    :param case_id: Optional case identifier.
    :return: Validated DetectionOutput contract.
    """
    return _default_service.detect(
        transaction=transaction,
        customer=customer,
        history=history,
        merchant=merchant,
        secondary_customer=secondary_customer,
        case_id=case_id,
    )


def detect_scenario(
    scenario: ScenarioResult,
    case_id: str | None = None,
) -> DetectionOutput:
    """Evaluate a complete synthetic ScenarioResult.

    :param scenario: The generated ScenarioResult.
    :param case_id: Optional case identifier.
    :return: Validated DetectionOutput contract.
    """
    return _default_service.detect_scenario(scenario=scenario, case_id=case_id)


__all__ = [
    "DetectionService",
    "HIGH_RISK_THRESHOLD",
    "LOCATION_DEVIATION_THRESHOLD_KM",
    "LOW_RISK_THRESHOLD",
    "MERCHANT_CHARGEBACK_THRESHOLD",
    "MODEL_NAME",
    "MODEL_VERSION",
    "RiskScoringModel",
    "UNUSUAL_AMOUNT_ABSOLUTE_THRESHOLD",
    "calculate_haversine_distance_km",
    "detect_scenario",
    "detect_transaction",
    "evaluate_all_anomalies",
]
