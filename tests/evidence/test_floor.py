"""Unit tests for the Phase 2.2 minimum-evidence floor, independent of the agent loop."""

from __future__ import annotations

from shared.contracts.detection import AnomalyTag
from shared.evidence.floor import (
    MINIMUM_EVIDENCE_FLOOR,
    is_floor_satisfied,
    missing_required_tools,
    required_tools_for_tags,
)


def test_floor_table_matches_contracts_v1_2_section_11_4() -> None:
    """1. Verify the floor table matches the frozen Contracts v1.2 S11.4 mapping exactly."""
    assert MINIMUM_EVIDENCE_FLOOR[AnomalyTag.NEW_DEVICE] == ("get_device_history",)
    assert MINIMUM_EVIDENCE_FLOOR[AnomalyTag.UNUSUAL_LOCATION] == ("get_ip_geovelocity",)
    assert MINIMUM_EVIDENCE_FLOOR[AnomalyTag.MERCHANT_RISK] == ("get_merchant_risk",)
    assert MINIMUM_EVIDENCE_FLOOR[AnomalyTag.UNUSUAL_AMOUNT] == ("get_behavioral_baseline",)
    assert MINIMUM_EVIDENCE_FLOOR[AnomalyTag.LINKED_ENTITY_ANOMALY] == ("get_linked_entities",)
    assert MINIMUM_EVIDENCE_FLOOR[AnomalyTag.KYC_ANOMALY] == ("get_mock_kyc_status",)


def test_required_tools_for_single_tag() -> None:
    """2. Verify a single anomaly tag maps to exactly its one required tool."""
    assert required_tools_for_tags([AnomalyTag.NEW_DEVICE]) == ["get_device_history"]


def test_required_tools_for_no_tags_is_empty() -> None:
    """3. Verify a clean transaction (no anomaly tags) has an empty floor."""
    assert required_tools_for_tags([]) == []


def test_required_tools_union_deduplicates_across_tags() -> None:
    """4. Verify multi-signal cases union each tag's requirement without duplicates."""
    required = required_tools_for_tags(
        [AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION, AnomalyTag.MERCHANT_RISK]
    )
    assert required == sorted(["get_device_history", "get_ip_geovelocity", "get_merchant_risk"])


def test_required_tools_for_tags_repeated_does_not_duplicate() -> None:
    """5. Verify repeating the same tag twice still produces a de-duplicated floor."""
    required = required_tools_for_tags([AnomalyTag.NEW_DEVICE, AnomalyTag.NEW_DEVICE])
    assert required == ["get_device_history"]


def test_is_floor_satisfied_true_when_all_required_tools_called() -> None:
    """6. Verify satisfaction is True once every required tool has been called."""
    required = required_tools_for_tags([AnomalyTag.NEW_DEVICE])
    assert is_floor_satisfied(["get_device_history"], required) is True


def test_is_floor_satisfied_true_with_extra_non_required_tools_called() -> None:
    """7. Verify calling additional (non-required) tools does not break satisfaction --
    this is exactly the branching-proof case: get_linked_entities is extra, not required."""
    required = required_tools_for_tags([AnomalyTag.NEW_DEVICE])
    assert is_floor_satisfied(["get_device_history", "get_linked_entities"], required) is True


def test_is_floor_satisfied_false_when_required_tool_missing() -> None:
    """8. Verify satisfaction is False if a required tool was never called."""
    required = required_tools_for_tags([AnomalyTag.NEW_DEVICE])
    assert is_floor_satisfied([], required) is False


def test_is_floor_satisfied_false_with_partial_multi_tag_coverage() -> None:
    """9. Verify multi-tag floors require every required tool, not just one of them."""
    required = required_tools_for_tags([AnomalyTag.NEW_DEVICE, AnomalyTag.MERCHANT_RISK])
    assert is_floor_satisfied(["get_device_history"], required) is False


def test_is_floor_satisfied_true_for_empty_floor_regardless_of_calls() -> None:
    """10. Verify a case with no anomaly tags is trivially floor-satisfied."""
    assert is_floor_satisfied([], []) is True
    assert is_floor_satisfied(["get_merchant_risk"], []) is True


def test_missing_required_tools_lists_only_uncalled_required_tools() -> None:
    """11. Verify missing_required_tools reports exactly what's outstanding, in floor order."""
    required = required_tools_for_tags(
        [AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION, AnomalyTag.MERCHANT_RISK]
    )
    missing = missing_required_tools(["get_device_history"], required)
    assert missing == ["get_ip_geovelocity", "get_merchant_risk"]


def test_missing_required_tools_empty_when_floor_satisfied() -> None:
    """12. Verify missing_required_tools is empty once the floor is satisfied."""
    required = required_tools_for_tags([AnomalyTag.NEW_DEVICE])
    assert missing_required_tools(["get_device_history"], required) == []
