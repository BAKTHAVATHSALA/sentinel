"""Unit tests for the Transaction contract and associated domain models."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from shared.contracts.transaction import (
    AuthorizationStage,
    Channel,
    Direction,
    Geo,
    PaymentRail,
    Transaction,
)


def _build_valid_transaction_payload() -> dict:
    """Build a baseline valid transaction payload dictionary for tests.

    :return: Dictionary containing all required fields for a valid V1 transaction.
    """
    return {
        "transaction_id": "tx_test_001",
        "customer_id": "cust_test_001",
        "account_id": "acc_test_001",
        "card_id": "card_test_001",
        "merchant_id": "merch_test_001",
        "amount": Decimal("199.99"),
        "currency": "USD",
        "timestamp": datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
        "payment_rail": PaymentRail.CARD_CNP,
        "direction": Direction.OUTGOING,
        "authorization_stage": AuthorizationStage.PRE_AUTH,
        "device_id": "dev_test_001",
        "ip_address": "198.51.100.42",
        "geo": Geo(lat=Decimal("37.7749"), lon=Decimal("-122.4194"), country="USA"),
        "channel": Channel.WEB,
        "merchant_category": "electronics",
        "card_present": False,
    }


def test_valid_v1_transaction_instantiation() -> None:
    """Test that a valid V1 Transaction can be instantiated with all required fields."""
    payload = _build_valid_transaction_payload()
    tx = Transaction(**payload)

    assert tx.transaction_id == "tx_test_001"
    assert tx.customer_id == "cust_test_001"
    assert tx.account_id == "acc_test_001"
    assert tx.card_id == "card_test_001"
    assert tx.merchant_id == "merch_test_001"
    assert tx.amount == Decimal("199.99")
    assert tx.currency == "USD"
    assert tx.timestamp == datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    assert tx.payment_rail == PaymentRail.CARD_CNP
    assert tx.direction == Direction.OUTGOING
    assert tx.authorization_stage == AuthorizationStage.PRE_AUTH
    assert tx.device_id == "dev_test_001"
    assert tx.ip_address == "198.51.100.42"
    assert isinstance(tx.geo, Geo)
    assert tx.geo.lat == Decimal("37.7749")
    assert tx.geo.lon == Decimal("-122.4194")
    assert tx.geo.country == "USA"
    assert tx.channel == Channel.WEB
    assert tx.merchant_category == "electronics"
    assert tx.card_present is False


def test_invalid_payment_rail_rejected() -> None:
    """Test that an invalid payment rail is rejected by validation."""
    payload = _build_valid_transaction_payload()
    payload["payment_rail"] = "UPI"

    with pytest.raises(ValidationError) as exc_info:
        Transaction(**payload)

    assert "payment_rail" in str(exc_info.value)


def test_invalid_direction_rejected() -> None:
    """Test that an invalid direction is rejected by validation."""
    payload = _build_valid_transaction_payload()
    payload["direction"] = "INCOMING"

    with pytest.raises(ValidationError) as exc_info:
        Transaction(**payload)

    assert "direction" in str(exc_info.value)


def test_invalid_authorization_stage_rejected() -> None:
    """Test that an invalid authorization stage is rejected by validation."""
    payload = _build_valid_transaction_payload()
    payload["authorization_stage"] = "DECLINED"

    with pytest.raises(ValidationError) as exc_info:
        Transaction(**payload)

    assert "authorization_stage" in str(exc_info.value)


def test_invalid_channel_rejected() -> None:
    """Test that an invalid channel is rejected by validation."""
    payload = _build_valid_transaction_payload()
    payload["channel"] = "ATM"

    with pytest.raises(ValidationError) as exc_info:
        Transaction(**payload)

    assert "channel" in str(exc_info.value)


@pytest.mark.parametrize(
    "field_to_omit",
    [
        "transaction_id",
        "customer_id",
        "account_id",
        "card_id",
        "merchant_id",
        "amount",
        "currency",
        "timestamp",
        "payment_rail",
        "direction",
        "authorization_stage",
        "device_id",
        "ip_address",
        "geo",
        "channel",
        "merchant_category",
        "card_present",
    ],
)
def test_required_fields_cannot_be_omitted(field_to_omit: str) -> None:
    """Test that omitting any required field raises a validation error."""
    payload = _build_valid_transaction_payload()
    del payload[field_to_omit]

    with pytest.raises(ValidationError) as exc_info:
        Transaction(**payload)

    assert field_to_omit in str(exc_info.value)


def test_card_present_accepts_boolean() -> None:
    """Test that card_present correctly accepts booleans and rejects non-boolean values."""
    payload = _build_valid_transaction_payload()

    payload["card_present"] = True
    tx_true = Transaction(**payload)
    assert tx_true.card_present is True

    payload["card_present"] = False
    tx_false = Transaction(**payload)
    assert tx_false.card_present is False

    payload["card_present"] = "not_a_boolean"
    with pytest.raises(ValidationError) as exc_info:
        Transaction(**payload)

    assert "card_present" in str(exc_info.value)


def test_geo_is_validated_as_geo_model() -> None:
    """Test that geo is strictly validated as a Geo model with lat, lon, and country."""
    payload = _build_valid_transaction_payload()

    # Valid dictionary representation
    payload["geo"] = {
        "lat": Decimal("40.7128"),
        "lon": Decimal("-74.0060"),
        "country": "USA",
    }
    tx = Transaction(**payload)
    assert isinstance(tx.geo, Geo)
    assert tx.geo.lat == Decimal("40.7128")
    assert tx.geo.lon == Decimal("-74.0060")
    assert tx.geo.country == "USA"

    # Missing required field in geo
    payload["geo"] = {
        "lat": Decimal("40.7128"),
        "lon": Decimal("-74.0060"),
    }
    with pytest.raises(ValidationError) as exc_info_missing:
        Transaction(**payload)
    assert "geo" in str(exc_info_missing.value)

    # Invalid type for geo
    payload["geo"] = "San Francisco, CA"
    with pytest.raises(ValidationError) as exc_info_type:
        Transaction(**payload)
    assert "geo" in str(exc_info_type.value)


def test_unexpected_field_rejected() -> None:
    """Test that unexpected or undeclared fields are rejected by Transaction validation."""
    payload = _build_valid_transaction_payload()
    payload["unexpected_field"] = "unexpected_value"

    with pytest.raises(ValidationError) as exc_info:
        Transaction(**payload)

    assert "unexpected_field" in str(exc_info.value)

