"""Unit tests for the Fact contract and associated FactQuality enum."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from shared.contracts.fact import Fact, FactQuality


def _build_valid_fact_payload() -> dict:
    """Build a baseline valid fact payload dictionary for testing.

    :return: Dictionary containing all required fields for a valid Fact.
    """
    return {
        "fact_id": "fact_001",
        "type": "device_history",
        "subject_id": "dev_12345",
        "value": {
            "first_seen_minutes_ago": 40,
            "associated_accounts_count": 2,
        },
        "source_tool": "get_device_history",
        "source_record_id": "rec_9999",
        "observed_at": datetime(2026, 9, 13, 11, 20, 0, tzinfo=timezone.utc),
        "retrieved_at": datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc),
        "quality": FactQuality.VERIFIED,
    }


def test_valid_fact_creation() -> None:
    """Test that a valid Fact can be created with all fields populated."""
    payload = _build_valid_fact_payload()
    fact = Fact(**payload)

    assert fact.fact_id == "fact_001"
    assert fact.type == "device_history"
    assert fact.subject_id == "dev_12345"
    assert fact.value == {
        "first_seen_minutes_ago": 40,
        "associated_accounts_count": 2,
    }
    assert fact.source_tool == "get_device_history"
    assert fact.source_record_id == "rec_9999"
    assert fact.observed_at == datetime(2026, 9, 13, 11, 20, 0, tzinfo=timezone.utc)
    assert fact.retrieved_at == datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    assert fact.quality == FactQuality.VERIFIED


def test_optional_source_record_id() -> None:
    """Test that source_record_id can be omitted or explicitly set to None."""
    payload = _build_valid_fact_payload()
    del payload["source_record_id"]

    fact_omitted = Fact(**payload)
    assert fact_omitted.source_record_id is None

    payload["source_record_id"] = None
    fact_none = Fact(**payload)
    assert fact_none.source_record_id is None

    payload["source_record_id"] = "rec_explicit"
    fact_provided = Fact(**payload)
    assert fact_provided.source_record_id == "rec_explicit"


@pytest.mark.parametrize(
    "quality_value",
    [
        FactQuality.VERIFIED,
        FactQuality.DERIVED,
        FactQuality.PARTIAL,
        "VERIFIED",
        "DERIVED",
        "PARTIAL",
    ],
)
def test_valid_quality_enum_values(quality_value: FactQuality | str) -> None:
    """Test that all defined FactQuality enum values are accepted."""
    payload = _build_valid_fact_payload()
    payload["quality"] = quality_value

    fact = Fact(**payload)
    assert fact.quality in {FactQuality.VERIFIED, FactQuality.DERIVED, FactQuality.PARTIAL}


def test_invalid_quality_value_rejected() -> None:
    """Test that an invalid quality value raises a validation error."""
    payload = _build_valid_fact_payload()
    payload["quality"] = "UNVERIFIED"

    with pytest.raises(ValidationError) as exc_info:
        Fact(**payload)

    assert "quality" in str(exc_info.value)


@pytest.mark.parametrize(
    "field_to_omit",
    [
        "fact_id",
        "type",
        "subject_id",
        "value",
        "source_tool",
        "observed_at",
        "retrieved_at",
        "quality",
    ],
)
def test_required_fields_cannot_be_omitted(field_to_omit: str) -> None:
    """Test that omitting any required field raises a validation error."""
    payload = _build_valid_fact_payload()
    del payload[field_to_omit]

    with pytest.raises(ValidationError) as exc_info:
        Fact(**payload)

    assert field_to_omit in str(exc_info.value)


def test_unexpected_fields_are_rejected() -> None:
    """Test that unexpected or undeclared fields are rejected by Fact validation."""
    payload = _build_valid_fact_payload()
    payload["extra_field"] = "not_allowed"

    with pytest.raises(ValidationError) as exc_info:
        Fact(**payload)

    assert "extra_field" in str(exc_info.value)
