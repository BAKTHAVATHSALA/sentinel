"""Deterministic anomaly tagging rules and geographic utilities for Sentinel V1."""

from datetime import datetime, timezone
from decimal import Decimal
import math

from shared.contracts.detection import AnomalyTag, RiskBand
from shared.contracts.tools import FraudReportTrend
from shared.contracts.transaction import Geo, Transaction
from shared.generator.models import CustomerProfile, MerchantProfile

# Explicit threshold constants
EARTH_RADIUS_KM = Decimal("6371.0")
LOCATION_DEVIATION_THRESHOLD_KM = Decimal("800.0")
UNUSUAL_AMOUNT_ABSOLUTE_THRESHOLD = Decimal("1500.00")
UNUSUAL_AMOUNT_SIGMA_MULTIPLIER = Decimal("25.0")
NIGHT_HOURS_START = 1  # 01:00 UTC
NIGHT_HOURS_END = 5    # 05:00 UTC
MAX_PLAUSIBLE_SPEED_KMH = Decimal("900.0")
MERCHANT_CHARGEBACK_THRESHOLD = Decimal("0.02")


def calculate_haversine_distance_km(geo1: Geo, geo2: Geo) -> Decimal:
    """Compute the great-circle distance between two geographic points using Haversine formula.

    :param geo1: Origin coordinates.
    :param geo2: Destination coordinates.
    :param returns: Distance in kilometers as Decimal.
    """
    lat1, lon1 = math.radians(float(geo1.lat)), math.radians(float(geo1.lon))
    lat2, lon2 = math.radians(float(geo2.lat)), math.radians(float(geo2.lon))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (math.sin(dlat / 2.0) ** 2) + math.cos(lat1) * math.cos(lat2) * (math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = float(EARTH_RADIUS_KM) * c
    return Decimal(str(round(distance, 2)))


def evaluate_new_device(
    transaction: Transaction,
    customer: CustomerProfile | None,
    history: list[Transaction] | None,
) -> tuple[bool, str | None]:
    """Check whether the transaction device is new or unrecognized.

    :param transaction: Candidate transaction.
    :param customer: Customer profile baseline.
    :param history: Historical transactions.
    :return: Tuple of (is_anomaly, reason).
    """
    if not customer:
        return False, None

    known_devices = {customer.primary_device_id}
    if history:
        for tx in history:
            known_devices.add(tx.device_id)

    if transaction.device_id not in known_devices:
        return True, f"Device '{transaction.device_id}' not found in customer historical device set"
    return False, None


def evaluate_unusual_location(
    transaction: Transaction,
    customer: CustomerProfile | None,
) -> tuple[bool, str | None]:
    """Check whether transaction location materially deviates from customer home baseline.

    :param transaction: Candidate transaction.
    :param customer: Customer profile baseline.
    :return: Tuple of (is_anomaly, reason).
    """
    if not customer:
        return False, None

    if transaction.geo.country != customer.home_geo.country:
        return True, f"Transaction country '{transaction.geo.country}' differs from baseline '{customer.home_geo.country}'"

    distance = calculate_haversine_distance_km(transaction.geo, customer.home_geo)
    if distance > LOCATION_DEVIATION_THRESHOLD_KM:
        return True, f"Distance of {distance}km exceeds baseline threshold of {LOCATION_DEVIATION_THRESHOLD_KM}km"

    return False, None


def evaluate_unusual_amount(
    transaction: Transaction,
    customer: CustomerProfile | None,
) -> tuple[bool, str | None]:
    """Check whether transaction amount is materially outside spending distribution.

    :param transaction: Candidate transaction.
    :param customer: Customer profile baseline.
    :return: Tuple of (is_anomaly, reason).
    """
    if not customer:
        return False, None

    sigma_cutoff = customer.typical_amount_mean + (customer.typical_amount_std * UNUSUAL_AMOUNT_SIGMA_MULTIPLIER)
    if transaction.amount >= UNUSUAL_AMOUNT_ABSOLUTE_THRESHOLD or transaction.amount >= sigma_cutoff:
        return True, f"Amount ${transaction.amount} exceeds baseline cutoff of ${sigma_cutoff}"

    return False, None


def evaluate_unusual_time(
    transaction: Transaction,
) -> tuple[bool, str | None]:
    """Check whether transaction occurs during atypical customer hours (deep night window).

    :param transaction: Candidate transaction.
    :return: Tuple of (is_anomaly, reason).
    """
    hour = transaction.timestamp.hour
    if NIGHT_HOURS_START <= hour <= NIGHT_HOURS_END:
        return True, f"Transaction hour {hour}:00 UTC is within atypical night window ({NIGHT_HOURS_START}-{NIGHT_HOURS_END})"
    return False, None


def evaluate_impossible_travel(
    transaction: Transaction,
    history: list[Transaction] | None,
) -> tuple[bool, str | None]:
    """Check whether implied speed between recent transactions exceeds plausible physical velocity.

    :param transaction: Candidate transaction.
    :param history: Historical transactions.
    :return: Tuple of (is_anomaly, reason).
    """
    if not history:
        return False, None

    # Compare against the most recent prior transaction
    prior_txs = [tx for tx in history if tx.timestamp < transaction.timestamp]
    if not prior_txs:
        return False, None

    most_recent = max(prior_txs, key=lambda tx: tx.timestamp)
    time_delta = (transaction.timestamp - most_recent.timestamp).total_seconds()
    if time_delta <= 0:
        return False, None

    elapsed_hours = Decimal(str(round(time_delta / 3600.0, 4)))
    distance_km = calculate_haversine_distance_km(most_recent.geo, transaction.geo)

    if elapsed_hours > Decimal("0.0"):
        velocity_kmh = distance_km / elapsed_hours
        if velocity_kmh > MAX_PLAUSIBLE_SPEED_KMH and distance_km > Decimal("200.0"):
            return True, f"Implied velocity of {velocity_kmh:.1f} km/h over {distance_km}km in {elapsed_hours}h exceeds max threshold {MAX_PLAUSIBLE_SPEED_KMH} km/h"

    return False, None


def evaluate_merchant_risk(
    merchant: MerchantProfile | None,
) -> tuple[bool, str | None]:
    """Check whether merchant exhibits seeded fraud or chargeback risk indicators.

    :param merchant: Merchant profile.
    :return: Tuple of (is_anomaly, reason).
    """
    if not merchant:
        return False, None

    if (
        merchant.chargeback_rate >= MERCHANT_CHARGEBACK_THRESHOLD
        or merchant.fraud_report_trend == FraudReportTrend.RISING
        or merchant.risk_band == RiskBand.HIGH
    ):
        return True, f"Merchant '{merchant.merchant_id}' has high risk indicators (chargeback={merchant.chargeback_rate}, trend={merchant.fraud_report_trend.value})"

    return False, None


def evaluate_linked_entity_anomaly(
    customer: CustomerProfile | None,
    secondary_customer: CustomerProfile | None,
) -> tuple[bool, str | None]:
    """Check whether customer is linked to another entity with anomalous/flagged status.

    :param customer: Primary customer profile.
    :param secondary_customer: Linked customer profile, if available.
    :return: Tuple of (is_anomaly, reason).
    """
    if not customer or not customer.linked_account_ids:
        return False, None

    if secondary_customer and secondary_customer.kyc_status in {"REVIEW", "FAILED"}:
        return True, f"Linked account '{secondary_customer.account_id}' has anomalous KYC status '{secondary_customer.kyc_status}'"

    return False, None


def evaluate_kyc_anomaly(
    customer: CustomerProfile | None,
) -> tuple[bool, str | None]:
    """Check whether customer KYC verification status is anomalous.

    :param customer: Customer profile.
    :return: Tuple of (is_anomaly, reason).
    """
    if not customer:
        return False, None

    if customer.kyc_status != "VERIFIED":
        return True, f"Customer KYC status is '{customer.kyc_status}' (expected 'VERIFIED')"

    return False, None


def evaluate_all_anomalies(
    transaction: Transaction,
    customer: CustomerProfile | None = None,
    history: list[Transaction] | None = None,
    merchant: MerchantProfile | None = None,
    secondary_customer: CustomerProfile | None = None,
) -> tuple[list[AnomalyTag], list[str]]:
    """Evaluate all 8 V1 anomaly rules deterministically.

    :param transaction: Transaction to evaluate.
    :param customer: Customer profile baseline.
    :param history: Prior transactions.
    :param merchant: Merchant profile.
    :param secondary_customer: Linked entity profile.
    :return: Tuple of (detected_tags, reasons).
    """
    tags: list[AnomalyTag] = []
    reasons: list[str] = []

    # 1. NEW_DEVICE
    is_new_dev, r_dev = evaluate_new_device(transaction, customer, history)
    if is_new_dev and r_dev:
        tags.append(AnomalyTag.NEW_DEVICE)
        reasons.append(r_dev)

    # 2. UNUSUAL_LOCATION
    is_unusual_loc, r_loc = evaluate_unusual_location(transaction, customer)
    if is_unusual_loc and r_loc:
        tags.append(AnomalyTag.UNUSUAL_LOCATION)
        reasons.append(r_loc)

    # 3. UNUSUAL_AMOUNT
    is_unusual_amt, r_amt = evaluate_unusual_amount(transaction, customer)
    if is_unusual_amt and r_amt:
        tags.append(AnomalyTag.UNUSUAL_AMOUNT)
        reasons.append(r_amt)

    # 4. UNUSUAL_TIME
    is_unusual_tm, r_tm = evaluate_unusual_time(transaction)
    if is_unusual_tm and r_tm:
        tags.append(AnomalyTag.UNUSUAL_TIME)
        reasons.append(r_tm)

    # 5. IMPOSSIBLE_TRAVEL
    is_imp_travel, r_trv = evaluate_impossible_travel(transaction, history)
    if is_imp_travel and r_trv:
        tags.append(AnomalyTag.IMPOSSIBLE_TRAVEL)
        reasons.append(r_trv)

    # 6. MERCHANT_RISK
    is_m_risk, r_m = evaluate_merchant_risk(merchant)
    if is_m_risk and r_m:
        tags.append(AnomalyTag.MERCHANT_RISK)
        reasons.append(r_m)

    # 7. LINKED_ENTITY_ANOMALY
    is_link_anom, r_link = evaluate_linked_entity_anomaly(customer, secondary_customer)
    if is_link_anom and r_link:
        tags.append(AnomalyTag.LINKED_ENTITY_ANOMALY)
        reasons.append(r_link)

    # 8. KYC_ANOMALY
    is_kyc_anom, r_kyc = evaluate_kyc_anomaly(customer)
    if is_kyc_anom and r_kyc:
        tags.append(AnomalyTag.KYC_ANOMALY)
        reasons.append(r_kyc)

    return tags, reasons
