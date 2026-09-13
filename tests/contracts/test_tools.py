"""Unit tests for all six evidence tool input and output contracts."""

from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from shared.contracts.detection import RiskBand
from shared.contracts.tools import (
    BehavioralBaselineInput,
    BehavioralBaselineOutput,
    DeviceHistoryInput,
    DeviceHistoryOutput,
    FraudReportTrend,
    IpGeovelocityInput,
    IpGeovelocityOutput,
    KycStatus,
    LinkedEntitiesInput,
    LinkedEntitiesOutput,
    MerchantRiskInput,
    MerchantRiskOutput,
    MockKycInput,
    MockKycOutput,
)


# Tool A: get_device_history
def test_device_history_contracts() -> None:
    """Test DeviceHistoryInput and DeviceHistoryOutput contracts."""
    inp = DeviceHistoryInput(customer_id="cust_01", device_id="dev_01")
    assert inp.customer_id == "cust_01"

    out = DeviceHistoryOutput(
        known_device=True,
        first_seen_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 9, 13, 11, 20, 0, tzinfo=timezone.utc),
        transaction_count=15,
        device_risk_signals=[{"signal": "MULTIPLE_ACCOUNTS", "count": 2}],
        source_record_ids=["rec_dev_100"],
    )
    assert out.known_device is True
    assert out.transaction_count == 15
    assert len(out.device_risk_signals) == 1


# Tool B: get_ip_geovelocity
def test_ip_geovelocity_contracts() -> None:
    """Test IpGeovelocityInput and IpGeovelocityOutput contracts."""
    inp = IpGeovelocityInput(
        customer_id="cust_01",
        current_ip="198.51.100.1",
        current_geo={"lat": Decimal("37.77"), "lon": Decimal("-122.41"), "country": "USA"},
        transaction_timestamp=datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert inp.current_ip == "198.51.100.1"

    out = IpGeovelocityOutput(
        previous_location={"lat": Decimal("40.71"), "lon": Decimal("-74.00"), "country": "USA"},
        previous_timestamp=datetime(2026, 9, 13, 11, 0, 0, tzinfo=timezone.utc),
        distance_km=Decimal("4129.5"),
        elapsed_hours=Decimal("1.0"),
        impossible_travel=True,
        source_record_ids=["rec_geo_200"],
    )
    assert out.impossible_travel is True
    assert out.distance_km == Decimal("4129.5")


# Tool C: get_behavioral_baseline
def test_behavioral_baseline_contracts() -> None:
    """Test BehavioralBaselineInput and BehavioralBaselineOutput contracts."""
    inp = BehavioralBaselineInput(
        customer_id="cust_01",
        transaction={"amount": Decimal("500.00"), "currency": "USD"},
    )
    assert inp.customer_id == "cust_01"

    out = BehavioralBaselineOutput(
        typical_amount=Decimal("75.00"),
        amount_deviation=Decimal("5.66"),
        typical_hours={"peak_hour_start": 9, "peak_hour_end": 21},
        time_deviation=Decimal("0.2"),
        historical_transaction_count=120,
        source_record_ids=["rec_base_300"],
    )
    assert out.typical_amount == Decimal("75.00")
    assert out.historical_transaction_count == 120


# Tool D: get_linked_entities
def test_linked_entities_contracts() -> None:
    """Test LinkedEntitiesInput and LinkedEntitiesOutput contracts."""
    inp = LinkedEntitiesInput(customer_id="cust_01", account_id="acc_01")
    assert inp.account_id == "acc_01"

    out = LinkedEntitiesOutput(
        linked_customers=["cust_02"],
        linked_accounts=["acc_99"],
        recent_anomalies=[{"anomaly": "SHARED_DEVICE", "seen": "2h ago"}],
        relationship_signals=[{"signal": "COMMON_IP"}],
        source_record_ids=["rec_link_400"],
    )
    assert len(out.linked_customers) == 1
    assert out.linked_accounts[0] == "acc_99"


# Tool E: get_merchant_risk (V1.1 domain scoped)
def test_merchant_risk_contracts_v1_1_domain_scoped() -> None:
    """Test MerchantRiskInput and MerchantRiskOutput using V1.1 domain-scoped shape."""
    inp = MerchantRiskInput(merchant_id="merch_01", customer_id="cust_01")
    assert inp.merchant_id == "merch_01"
    assert inp.customer_id == "cust_01"

    out = MerchantRiskOutput(
        category="electronics",
        onboarding_date=date(2025, 1, 15),
        chargeback_rate=Decimal("0.023"),
        recent_fraud_report_count=3,
        fraud_report_trend=FraudReportTrend.RISING,
        customer_prior_transactions_with_merchant=0,
        risk_band=RiskBand.HIGH,
    )
    assert out.category == "electronics"
    assert out.recent_fraud_report_count == 3
    assert out.fraud_report_trend == FraudReportTrend.RISING
    assert out.customer_prior_transactions_with_merchant == 0
    assert out.risk_band == RiskBand.HIGH


# Tool F: get_mock_kyc_status
def test_mock_kyc_status_contracts() -> None:
    """Test MockKycInput and MockKycOutput contracts."""
    inp = MockKycInput(customer_id="cust_01")
    assert inp.customer_id == "cust_01"

    out = MockKycOutput(
        kyc_status=KycStatus.VERIFIED,
        kyc_flags=[],
        source_record_ids=["rec_kyc_500"],
    )
    assert out.kyc_status == KycStatus.VERIFIED
    assert out.kyc_flags == []


def test_tool_contracts_reject_extra_fields() -> None:
    """Test that extra fields on tool contracts are rejected."""
    with pytest.raises(ValidationError):
        DeviceHistoryInput(customer_id="c1", device_id="d1", extra_param="bad")  # type: ignore

    with pytest.raises(ValidationError):
        MerchantRiskInput(merchant_id="m1", customer_id="c1", unlisted_key=123)  # type: ignore
