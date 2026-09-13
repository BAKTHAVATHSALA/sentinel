"""Deterministic entity and profile generators for Sentinel V1."""

from datetime import date
from decimal import Decimal
import random

from shared.contracts.detection import RiskBand
from shared.contracts.tools import FraudReportTrend
from shared.contracts.transaction import Geo
from shared.generator.models import CustomerProfile, MerchantProfile

# Curated reference cities for realistic synthetic geo locations
CITIES: list[tuple[Decimal, Decimal, str]] = [
    (Decimal("40.7128"), Decimal("-74.0060"), "USA"),  # New York
    (Decimal("37.7749"), Decimal("-122.4194"), "USA"),  # San Francisco
    (Decimal("51.5074"), Decimal("-0.1278"), "GBR"),  # London
    (Decimal("35.6762"), Decimal("139.6503"), "JPN"),  # Tokyo
    (Decimal("41.8781"), Decimal("-87.6298"), "USA"),  # Chicago
    (Decimal("25.7617"), Decimal("-80.1918"), "USA"),  # Miami
    (Decimal("34.0522"), Decimal("-118.2437"), "USA"),  # Los Angeles
]

MERCHANT_CATEGORIES: list[str] = [
    "electronics",
    "digital_goods",
    "travel_airline",
    "retail_apparel",
    "groceries",
    "entertainment",
]


def create_customer_profile(
    customer_id: str,
    rng: random.Random,
    city_idx: int = 0,
    tenure_months: int = 18,
    mean_amount: Decimal = Decimal("75.00"),
    std_amount: Decimal = Decimal("25.00"),
    kyc_status: str = "VERIFIED",
) -> CustomerProfile:
    """Generate a deterministic synthetic customer profile.

    :param customer_id: Unique customer ID.
    :param rng: Seeded random generator.
    :param city_idx: City index from curated list.
    :param tenure_months: Customer relationship tenure in months.
    :param mean_amount: Average transaction amount.
    :param std_amount: Standard deviation for amounts.
    :param kyc_status: Verification status.
    :return: A fully constructed CustomerProfile.
    """
    account_num = rng.randint(1000, 9999)
    card_num = rng.randint(1000, 9999)
    device_num = rng.randint(10000, 99999)
    ip_octet = rng.randint(10, 240)

    city = CITIES[city_idx % len(CITIES)]
    home_geo = Geo(lat=city[0], lon=city[1], country=city[2])

    favorite_merchants = [
        f"merch_favorite_{rng.randint(100, 999)}" for _ in range(3)
    ]

    return CustomerProfile(
        customer_id=customer_id,
        account_id=f"acc_{account_num}",
        card_id=f"card_{card_num}",
        tenure_months=tenure_months,
        primary_device_id=f"dev_{device_num}",
        primary_ip=f"198.51.100.{ip_octet}",
        home_geo=home_geo,
        typical_amount_mean=mean_amount,
        typical_amount_std=std_amount,
        favorite_merchants=favorite_merchants,
        kyc_status=kyc_status,
        linked_account_ids=[],
    )


def create_merchant_profile(
    merchant_id: str,
    category: str = "electronics",
    risk_band: RiskBand = RiskBand.LOW,
    chargeback_rate: Decimal = Decimal("0.005"),
    recent_fraud_reports: int = 0,
    fraud_trend: FraudReportTrend = FraudReportTrend.STABLE,
    onboarding_date: date = date(2024, 1, 1),
) -> MerchantProfile:
    """Generate a deterministic synthetic merchant profile.

    :param merchant_id: Unique merchant identifier.
    :param category: Merchant business category.
    :param risk_band: Assigned risk band.
    :param chargeback_rate: Historical chargeback percentage.
    :param recent_fraud_reports: Number of recent fraud reports.
    :param fraud_trend: Trend direction for fraud reports.
    :param onboarding_date: Date of onboarding.
    :return: A fully constructed MerchantProfile.
    """
    return MerchantProfile(
        merchant_id=merchant_id,
        category=category,
        onboarding_date=onboarding_date,
        chargeback_rate=chargeback_rate,
        recent_fraud_report_count=recent_fraud_reports,
        fraud_report_trend=fraud_trend,
        risk_band=risk_band,
    )
