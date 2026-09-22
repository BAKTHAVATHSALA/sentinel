"""Domain models and metadata structures for the synthetic transaction generator."""

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from shared.contracts.detection import RiskBand
from shared.contracts.tools import FraudReportTrend
from shared.contracts.transaction import Geo, Transaction


class CustomerProfile(BaseModel):
    """Synthetic customer profile modeling historical baseline behavior."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str
    account_id: str
    card_id: str
    tenure_months: int
    primary_device_id: str
    primary_ip: str
    home_geo: Geo
    typical_amount_mean: Decimal
    typical_amount_std: Decimal
    favorite_merchants: list[str]
    kyc_status: str
    linked_account_ids: list[str] = []


class MerchantProfile(BaseModel):
    """Synthetic merchant profile modeling risk and category behavior."""

    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    category: str
    onboarding_date: date
    chargeback_rate: Decimal
    recent_fraud_report_count: int
    fraud_report_trend: FraudReportTrend
    risk_band: RiskBand


class ScenarioResult(BaseModel):
    """Complete container for a generated scenario with metadata and transactions."""

    model_config = ConfigDict(extra="forbid")

    scenario_name: str
    target_transaction: Transaction
    baseline_transactions: list[Transaction]
    customer_profile: CustomerProfile
    merchant_profile: MerchantProfile
    secondary_profile: CustomerProfile | None = None
    metadata: dict[str, object]
