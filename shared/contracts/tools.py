"""Evidence tool input and output contracts for Sentinel V1."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict

from shared.contracts.detection import RiskBand
from shared.contracts.transaction import Transaction


# Tool A: get_device_history
class DeviceHistoryInput(BaseModel):
    """Input parameters for get_device_history evidence tool."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str
    device_id: str


class DeviceHistoryOutput(BaseModel):
    """Output evidence returned by get_device_history tool."""

    model_config = ConfigDict(extra="forbid")

    known_device: bool
    first_seen_at: datetime
    last_seen_at: datetime
    transaction_count: int
    device_risk_signals: list[dict[str, object]]
    source_record_ids: list[str]


# Tool B: get_ip_geovelocity
class IpGeovelocityInput(BaseModel):
    """Input parameters for get_ip_geovelocity evidence tool."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str
    current_ip: str
    current_geo: dict[str, object]
    transaction_timestamp: datetime


class IpGeovelocityOutput(BaseModel):
    """Output evidence returned by get_ip_geovelocity tool."""

    model_config = ConfigDict(extra="forbid")

    previous_location: dict[str, object]
    previous_timestamp: datetime
    distance_km: Decimal
    elapsed_hours: Decimal
    impossible_travel: bool
    source_record_ids: list[str]


# Tool C: get_behavioral_baseline
class BehavioralBaselineInput(BaseModel):
    """Input parameters for get_behavioral_baseline evidence tool."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str
    transaction: Transaction | dict[str, object]


class BehavioralBaselineOutput(BaseModel):
    """Output evidence returned by get_behavioral_baseline tool."""

    model_config = ConfigDict(extra="forbid")

    typical_amount: Decimal
    amount_deviation: Decimal
    typical_hours: dict[str, object]
    time_deviation: Decimal
    historical_transaction_count: int
    source_record_ids: list[str]


# Tool D: get_linked_entities
class LinkedEntitiesInput(BaseModel):
    """Input parameters for get_linked_entities evidence tool."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str
    account_id: str


class LinkedEntitiesOutput(BaseModel):
    """Output evidence returned by get_linked_entities tool."""

    model_config = ConfigDict(extra="forbid")

    linked_customers: list[str]
    linked_accounts: list[str]
    recent_anomalies: list[dict[str, object]]
    relationship_signals: list[dict[str, object]]
    source_record_ids: list[str]


# Tool E: get_merchant_risk (Authoritative V1.1 Domain Scoped)
class FraudReportTrend(str, Enum):
    """Observed trend of recent fraud reports for a merchant."""

    RISING = "RISING"
    STABLE = "STABLE"
    FALLING = "FALLING"


class MerchantRiskInput(BaseModel):
    """Input parameters for get_merchant_risk evidence tool."""

    model_config = ConfigDict(extra="forbid")

    merchant_id: str
    customer_id: str


class MerchantRiskOutput(BaseModel):
    """Output evidence returned by get_merchant_risk tool in V1 domain scope."""

    model_config = ConfigDict(extra="forbid")

    category: str
    onboarding_date: date
    chargeback_rate: Decimal
    recent_fraud_report_count: int
    fraud_report_trend: FraudReportTrend
    customer_prior_transactions_with_merchant: int
    risk_band: RiskBand


# Tool F: get_mock_kyc_status
class KycStatus(str, Enum):
    """Verification status of customer KYC."""

    VERIFIED = "VERIFIED"
    REVIEW = "REVIEW"
    FAILED = "FAILED"


class MockKycInput(BaseModel):
    """Input parameters for get_mock_kyc_status evidence tool."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str


class MockKycOutput(BaseModel):
    """Output evidence returned by get_mock_kyc_status tool."""

    model_config = ConfigDict(extra="forbid")

    kyc_status: KycStatus
    kyc_flags: list[str]
    source_record_ids: list[str]
