"""Unit tests for the synthetic transaction generator and seeded scenarios."""

from datetime import timezone
from decimal import Decimal
import pytest

from shared.contracts.transaction import (
    AuthorizationStage,
    Channel,
    Direction,
    PaymentRail,
    Transaction,
)
from shared.generator import (
    CustomerProfile,
    ScenarioResult,
    generate_scenario,
    generate_transactions,
    seeded_demo_case,
)


def test_generated_transactions_validate_against_transaction_model() -> None:
    """1. Test that all generated transactions validate strictly against Transaction model."""
    txs = generate_transactions(count=15, seed=123)
    assert len(txs) == 15
    for tx in txs:
        assert isinstance(tx, Transaction)


def test_same_seed_produces_identical_dataset() -> None:
    """2. Test that identical seeds produce byte-for-byte identical datasets."""
    txs_a = generate_transactions(count=20, seed=999)
    txs_b = generate_transactions(count=20, seed=999)

    assert len(txs_a) == len(txs_b)
    for tx_a, tx_b in zip(txs_a, txs_b):
        assert tx_a.model_dump() == tx_b.model_dump()


def test_different_seeds_produce_different_datasets() -> None:
    """3. Test that differing seeds produce distinct datasets."""
    txs_a = generate_transactions(count=10, seed=111)
    txs_b = generate_transactions(count=10, seed=222)

    ids_a = [tx.transaction_id for tx in txs_a]
    ids_b = [tx.transaction_id for tx in txs_b]
    amounts_a = [tx.amount for tx in txs_a]
    amounts_b = [tx.amount for tx in txs_b]

    assert amounts_a != amounts_b or ids_a != ids_b


def test_requested_transaction_count_is_respected() -> None:
    """4. Test that requested transaction counts are exact."""
    for requested in [1, 5, 23, 50]:
        txs = generate_transactions(count=requested, seed=42)
        assert len(txs) == requested


def test_transaction_ids_are_unique() -> None:
    """5. Test that all generated transaction IDs in a dataset are unique."""
    txs = generate_transactions(count=40, seed=77)
    ids = [tx.transaction_id for tx in txs]
    assert len(ids) == len(set(ids))


def test_required_v1_domain_fields_are_always_correct() -> None:
    """6. Test domain constraints for V1: CARD_CNP, OUTGOING, PRE_AUTH, card_present=False."""
    txs = generate_transactions(count=30, seed=42)
    for tx in txs:
        assert tx.payment_rail == PaymentRail.CARD_CNP
        assert tx.direction == Direction.OUTGOING
        assert tx.authorization_stage == AuthorizationStage.PRE_AUTH
        assert tx.card_present is False
        assert tx.channel in {Channel.WEB, Channel.MOBILE}


def test_amounts_are_decimal() -> None:
    """7. Test that transaction amount is Decimal with at least 2 decimal places."""
    txs = generate_transactions(count=20, seed=42)
    for tx in txs:
        assert isinstance(tx.amount, Decimal)
        assert tx.amount > Decimal("0.00")
        assert tx.amount.as_tuple().exponent == -2


def test_timestamps_are_utc_timezone_aware() -> None:
    """8. Test that all timestamps are timezone-aware and set to UTC."""
    txs = generate_transactions(count=20, seed=42)
    for tx in txs:
        assert tx.timestamp.tzinfo is not None
        assert tx.timestamp.tzinfo == timezone.utc


def test_geo_values_are_valid() -> None:
    """9. Test that geographic coordinates are valid decimals and country is valid."""
    txs = generate_transactions(count=20, seed=42)
    for tx in txs:
        assert isinstance(tx.geo.lat, Decimal)
        assert isinstance(tx.geo.lon, Decimal)
        assert -90 <= tx.geo.lat <= 90
        assert -180 <= tx.geo.lon <= 180
        assert len(tx.geo.country) == 3


def test_customer_account_card_relationships_are_consistent() -> None:
    """10. Test that transactions for a customer maintain stable account and card IDs."""
    txs = generate_transactions(count=30, seed=42, customer_count=2)
    by_customer: dict[str, set[tuple[str, str]]] = {}
    for tx in txs:
        by_customer.setdefault(tx.customer_id, set()).add((tx.account_id, tx.card_id))

    for cust_id, accounts_cards in by_customer.items():
        assert len(accounts_cards) == 1, f"Customer {cust_id} has inconsistent account/card IDs"


def test_normal_baseline_scenario_is_reproducible() -> None:
    """11. Test that baseline generation is reproducible."""
    sc_a = generate_scenario("NEW_DEVICE", seed=10)
    sc_b = generate_scenario("NEW_DEVICE", seed=10)

    assert len(sc_a.baseline_transactions) == len(sc_b.baseline_transactions)
    for t_a, t_b in zip(sc_a.baseline_transactions, sc_b.baseline_transactions):
        assert t_a.transaction_id == t_b.transaction_id
        assert t_a.amount == t_b.amount


@pytest.mark.parametrize(
    "scenario_name",
    [
        "NEW_DEVICE",
        "UNUSUAL_LOCATION",
        "UNUSUAL_AMOUNT",
        "UNUSUAL_TIME",
        "IMPOSSIBLE_TRAVEL",
        "MERCHANT_RISK",
        "LINKED_ENTITY_ANOMALY",
        "KYC_ANOMALY",
    ],
)
def test_all_eight_seeded_scenarios_are_valid_and_reproducible(scenario_name: str) -> None:
    """12. Test that each of the 8 required seeded scenarios generates valid transactions."""
    sc1 = generate_scenario(scenario_name, seed=100)
    sc2 = generate_scenario(scenario_name, seed=100)

    assert sc1.scenario_name == scenario_name
    assert isinstance(sc1.target_transaction, Transaction)
    assert sc1.target_transaction.model_dump() == sc2.target_transaction.model_dump()
    assert sc1.metadata["seeded_anomaly"] == scenario_name


def test_flagship_demo_scenario_contains_all_architectural_requirements() -> None:
    """13. Test flagship demo scenario for: new device, unusual location, merchant risk, branching hook."""
    demo = seeded_demo_case(seed=42)

    assert isinstance(demo, ScenarioResult)
    target = demo.target_transaction
    assert isinstance(target, Transaction)

    # V1 domain constraints
    assert target.payment_rail == PaymentRail.CARD_CNP
    assert target.direction == Direction.OUTGOING
    assert target.authorization_stage == AuthorizationStage.PRE_AUTH
    assert target.card_present is False

    # 1. New device relationship
    assert target.device_id != demo.customer_profile.primary_device_id
    assert demo.metadata["device_details"]["first_seen_minutes_prior"] == 40

    # 2. Unusual location setup (Miami vs New York established baseline)
    assert demo.metadata["location_details"]["established_home_city"] == "New York, USA"
    assert demo.metadata["location_details"]["transaction_city"] == "Miami, USA"

    # 3. Merchant-risk setup (rising trend, 3 reports in last 30 days)
    assert demo.merchant_profile.recent_fraud_report_count == 3
    assert demo.merchant_profile.fraud_report_trend.value == "RISING"

    # 4. Cross-account/device relationship needed for branching hook
    linkage = demo.metadata["device_details"]["cross_account_linkage"]
    assert demo.secondary_profile is not None
    assert linkage["linked_customer_id"] == demo.secondary_profile.customer_id
    assert linkage["linked_account_id"] == demo.secondary_profile.account_id
    assert linkage["seen_hours_prior"] == 2
