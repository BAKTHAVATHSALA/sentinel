"""Unit tests for the deterministic synthetic investigation context
(shared/generator/synthesis.py) -- "unknown transaction != automatic fraud".

Architecture under test: customer/merchant baselines are a STABLE function
of identity alone (never regenerated to match a specific transaction); the
real transaction is compared against that fixed baseline by the existing,
unmodified pipeline. No network dependency: pure generation logic only.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from decimal import Decimal

from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
from shared.detection import detect_transaction
from shared.evidence.fixtures import build_fixture_context, resolve_behavioral_baseline, resolve_merchant_risk
from shared.generator import synthesis
from shared.generator.synthesis import (
    derive_customer_baseline,
    derive_linked_entity,
    derive_merchant_profile,
    synthesize_scenario_for_transaction,
)


def _make_transaction(**overrides: object) -> Transaction:
    fields: dict[str, object] = {
        "transaction_id": "tx_unknown_001",
        "customer_id": "cust_unknown_001",
        "account_id": "acc_unknown_001",
        "card_id": "card_unknown_001",
        "merchant_id": "merch_unknown_001",
        "amount": Decimal("899.99"),
        "currency": "USD",
        "timestamp": datetime(2026, 9, 18, 14, 0, 0, tzinfo=timezone.utc),
        "payment_rail": PaymentRail.CARD_CNP,
        "direction": Direction.OUTGOING,
        "authorization_stage": AuthorizationStage.PRE_AUTH,
        "device_id": "device_unknown_001",
        "ip_address": "198.51.100.50",
        "geo": Geo(lat=Decimal("25.7617"), lon=Decimal("-80.1918"), country="USA"),
        "channel": Channel.WEB,
        "merchant_category": "electronics",
        "card_present": False,
    }
    fields.update(overrides)
    return Transaction(**fields)


# --- No outcome/risk mapping (structural) ---------------------------------


def test_baseline_derivation_functions_take_only_identity_strings() -> None:
    """No function in this module can receive an intended risk/outcome --
    their signatures only accept identity fields (IDs), never amount,
    device/geo values, or a risk/outcome flag."""
    customer_params = set(inspect.signature(derive_customer_baseline).parameters)
    assert customer_params == {"customer_id", "account_id", "card_id"}

    merchant_params = set(inspect.signature(derive_merchant_profile).parameters)
    assert merchant_params == {"merchant_id"}

    linked_params = set(inspect.signature(derive_linked_entity).parameters)
    assert linked_params == {"customer_id", "account_id", "card_id"}


def test_no_disposition_like_key_in_synthesized_metadata() -> None:
    scenario = synthesize_scenario_for_transaction(_make_transaction())
    disposition_like_keys = {"expected_policy_outcome", "outcome", "disposition", "final_state", "is_fraud", "risk_level"}
    assert not (disposition_like_keys & scenario.metadata.keys())


# --- Stable, identity-only customer baseline ------------------------------


def test_same_customer_identity_produces_byte_identical_profile_across_different_transactions() -> None:
    """The customer baseline must NOT be regenerated per transaction --
    two different transactions from the same customer_id/account_id/card_id
    must see the exact same CustomerProfile object, even though the
    transactions themselves differ in every other field."""
    customer1, devices1 = derive_customer_baseline("cust_a", "acc_a", "card_a")
    customer2, devices2 = derive_customer_baseline("cust_a", "acc_a", "card_a")

    assert customer1 == customer2
    assert devices1 == devices2

    # Confirmed again via the full synthesis entry point with two
    # completely different transactions for the same identity.
    tx1 = _make_transaction(transaction_id="tx_1", amount=Decimal("10.00"), merchant_id="merch_x")
    tx2 = _make_transaction(transaction_id="tx_2", amount=Decimal("4899.00"), merchant_id="merch_y", device_id="some_other_device")
    scenario1 = synthesize_scenario_for_transaction(tx1)
    scenario2 = synthesize_scenario_for_transaction(tx2)
    assert scenario1.customer_profile == scenario2.customer_profile


def test_different_customer_identities_produce_independent_profiles() -> None:
    customer_a, _ = derive_customer_baseline("cust_a", "acc_a", "card_a")
    customer_b, _ = derive_customer_baseline("cust_b", "acc_b", "card_b")
    assert customer_a != customer_b


def test_customer_baseline_is_deterministically_repeatable_across_separate_calls() -> None:
    first, first_devices = derive_customer_baseline("cust_repeat", "acc_repeat", "card_repeat")
    second, second_devices = derive_customer_baseline("cust_repeat", "acc_repeat", "card_repeat")
    assert first == second
    assert first_devices == second_devices


def test_kyc_status_is_always_verified_never_manufactured_as_anomalous() -> None:
    """A hard-risk tag (KYC_ANOMALY) must never be manufactured merely
    because a transaction is unknown -- there is no real KYC signal to
    derive from an uploaded transaction, so the primary synthetic customer
    is always VERIFIED."""
    for i in range(20):
        customer, _ = derive_customer_baseline(f"cust_kyc_check_{i}", f"acc_{i}", f"card_{i}")
        assert customer.kyc_status == "VERIFIED"


# --- Stable, identity-only merchant profile -------------------------------


def test_same_merchant_identity_produces_byte_identical_profile_across_different_transactions() -> None:
    merchant1 = derive_merchant_profile("merch_a")
    merchant2 = derive_merchant_profile("merch_a")
    assert merchant1 == merchant2

    tx1 = _make_transaction(transaction_id="tx_1", customer_id="cust_1", merchant_id="merch_a")
    tx2 = _make_transaction(transaction_id="tx_2", customer_id="cust_2", merchant_id="merch_a", amount=Decimal("12.00"))
    scenario1 = synthesize_scenario_for_transaction(tx1)
    scenario2 = synthesize_scenario_for_transaction(tx2)
    assert scenario1.merchant_profile == scenario2.merchant_profile


def test_different_merchant_identities_produce_independent_profiles() -> None:
    merchant_a = derive_merchant_profile("merch_a")
    merchant_b = derive_merchant_profile("merch_b")
    assert merchant_a != merchant_b


def test_merchant_profile_never_derived_from_the_transactions_own_category_field() -> None:
    """Merchant profile is derived only from merchant_id -- the transaction's
    own merchant_category field must have zero influence on it."""
    tx1 = _make_transaction(merchant_id="merch_fixed", merchant_category="electronics")
    tx2 = _make_transaction(merchant_id="merch_fixed", merchant_category="groceries")
    scenario1 = synthesize_scenario_for_transaction(tx1)
    scenario2 = synthesize_scenario_for_transaction(tx2)
    assert scenario1.merchant_profile == scenario2.merchant_profile


# --- Transaction-vs-baseline comparison (not the baseline itself) can differ


def test_comparison_result_differs_across_transactions_while_baseline_stays_identical() -> None:
    """Same customer, two different transactions: the underlying baseline
    is identical, but whether each transaction matches it (and therefore
    which anomaly tags Detection derives) is allowed -- expected -- to
    differ, because the transactions themselves differ."""
    customer, known_devices = derive_customer_baseline("cust_compare", "acc_compare", "card_compare")

    matching_tx = _make_transaction(
        transaction_id="tx_match",
        customer_id="cust_compare",
        account_id="acc_compare",
        card_id="card_compare",
        device_id=known_devices[0],
        geo=customer.home_geo,
        amount=customer.typical_amount_mean,
    )
    deviating_tx = _make_transaction(
        transaction_id="tx_deviate",
        customer_id="cust_compare",
        account_id="acc_compare",
        card_id="card_compare",
        device_id="device_never_seen_before",
        geo=Geo(lat=Decimal("35.6762"), lon=Decimal("139.6503"), country="JPN"),
    )

    scenario_match = synthesize_scenario_for_transaction(matching_tx)
    scenario_deviate = synthesize_scenario_for_transaction(deviating_tx)

    # Same baseline both times.
    assert scenario_match.customer_profile == scenario_deviate.customer_profile

    detection_match = detect_transaction(
        transaction=matching_tx,
        customer=scenario_match.customer_profile,
        history=scenario_match.baseline_transactions,
        merchant=scenario_match.merchant_profile,
        case_id="case_match",
    )
    detection_deviate = detect_transaction(
        transaction=deviating_tx,
        customer=scenario_deviate.customer_profile,
        history=scenario_deviate.baseline_transactions,
        merchant=scenario_deviate.merchant_profile,
        case_id="case_deviate",
    )

    assert detection_match.anomaly_tags == []
    assert "NEW_DEVICE" in [t.value for t in detection_deviate.anomaly_tags]
    assert "UNUSUAL_LOCATION" in [t.value for t in detection_deviate.anomaly_tags]


def test_known_device_pool_has_more_than_one_device() -> None:
    _, known_devices = derive_customer_baseline("cust_multi_device", "acc_x", "card_x")
    assert len(known_devices) >= 2
    assert len(set(known_devices)) == len(known_devices)


# --- No fabricated linked entity / secondary profile by default ----------


def test_linked_entity_is_deterministic_and_never_transaction_derived() -> None:
    first = derive_linked_entity("cust_link_check", "acc_x", "card_x")
    second = derive_linked_entity("cust_link_check", "acc_x", "card_x")
    assert first == second


def test_most_customers_have_no_fabricated_linked_entity() -> None:
    none_count = sum(1 for i in range(50) if derive_linked_entity(f"cust_{i}", f"acc_{i}", f"card_{i}") is None)
    assert none_count > 25  # majority should be None -- not fabricated for most identities


# --- Target transaction integrity -----------------------------------------


def test_target_transaction_is_the_real_submitted_transaction_unaltered() -> None:
    tx = _make_transaction()
    scenario = synthesize_scenario_for_transaction(tx)
    assert scenario.target_transaction == tx


def test_baseline_transactions_all_predate_the_target_transaction() -> None:
    tx = _make_transaction()
    scenario = synthesize_scenario_for_transaction(tx)
    assert len(scenario.baseline_transactions) > 0
    assert all(baseline_tx.timestamp < tx.timestamp for baseline_tx in scenario.baseline_transactions)


# --- Downstream pipeline compatibility -------------------------------------


def test_existing_evidence_tools_can_consume_the_synthesized_context() -> None:
    tx = _make_transaction()
    scenario = synthesize_scenario_for_transaction(tx)
    ctx = build_fixture_context(scenario, case_id="case_test_synth")

    baseline_result = resolve_behavioral_baseline(ctx, tx.customer_id, tx)
    assert "typical_amount" in baseline_result

    merchant_result = resolve_merchant_risk(ctx, tx.merchant_id, tx.customer_id)
    assert "risk_band" in merchant_result


def test_existing_detection_runs_unmodified_against_synthesized_context() -> None:
    tx = _make_transaction()
    scenario = synthesize_scenario_for_transaction(tx)

    detection = detect_transaction(
        transaction=tx,
        customer=scenario.customer_profile,
        history=scenario.baseline_transactions,
        merchant=scenario.merchant_profile,
        secondary_customer=scenario.secondary_profile,
        case_id="case_test_synth_detect",
    )

    # The resolver never decides an outcome -- detection is free to produce
    # zero or more anomaly tags based purely on the real deltas between tx
    # and the synthesized baseline.
    assert isinstance(detection.anomaly_tags, list)
    assert detection.risk_band is not None


def test_synthesize_scenario_for_transaction_is_deterministically_repeatable() -> None:
    tx = _make_transaction()
    first = synthesis.synthesize_scenario_for_transaction(tx)
    second = synthesis.synthesize_scenario_for_transaction(tx)
    assert first.customer_profile == second.customer_profile
    assert first.merchant_profile == second.merchant_profile
    assert first.baseline_transactions == second.baseline_transactions
