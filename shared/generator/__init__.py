"""Synthetic Transaction Generator package for Sentinel V1."""

from datetime import datetime, timezone
import random

from shared.contracts.transaction import Transaction
from shared.generator.models import CustomerProfile, MerchantProfile, ScenarioResult
from shared.generator.profiles import create_customer_profile, create_merchant_profile
from shared.generator.scenarios import (
    generate_impossible_travel_scenario,
    generate_kyc_anomaly_scenario,
    generate_linked_entity_anomaly_scenario,
    generate_merchant_risk_scenario,
    generate_new_device_scenario,
    generate_unusual_amount_scenario,
    generate_unusual_location_scenario,
    generate_unusual_time_scenario,
    seeded_demo_case,
)
from shared.generator.transactions import generate_normal_transactions

SCENARIO_GENERATORS = {
    "NEW_DEVICE": generate_new_device_scenario,
    "UNUSUAL_LOCATION": generate_unusual_location_scenario,
    "UNUSUAL_AMOUNT": generate_unusual_amount_scenario,
    "UNUSUAL_TIME": generate_unusual_time_scenario,
    "IMPOSSIBLE_TRAVEL": generate_impossible_travel_scenario,
    "MERCHANT_RISK": generate_merchant_risk_scenario,
    "LINKED_ENTITY_ANOMALY": generate_linked_entity_anomaly_scenario,
    "KYC_ANOMALY": generate_kyc_anomaly_scenario,
}


def generate_transactions(
    count: int = 20,
    seed: int = 42,
    customer_count: int = 3,
) -> list[Transaction]:
    """Generate a reproducible list of normal synthetic V1 transactions.

    :param count: Total number of transactions requested.
    :param seed: Deterministic seed for reproducible generation.
    :param customer_count: Number of distinct customer profiles to generate.
    :return: List of valid Transaction models.
    """
    rng = random.Random(seed)
    customers = [
        create_customer_profile(f"cust_gen_{i:03d}", rng, city_idx=i)
        for i in range(max(1, customer_count))
    ]
    merchants = [
        create_merchant_profile(f"merch_gen_{j:02d}")
        for j in range(4)
    ]

    all_txs: list[Transaction] = []
    base_time = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)

    # Distribute count across customers
    per_cust = max(1, count // len(customers))
    for idx, customer in enumerate(customers):
        tx_needed = per_cust if idx < len(customers) - 1 else count - len(all_txs)
        if tx_needed > 0:
            txs = generate_normal_transactions(
                customer, merchants, count=tx_needed, rng=rng, base_time=base_time
            )
            all_txs.extend(txs)

    # Ensure exact requested count and unique IDs
    result = all_txs[:count]
    return result


def generate_scenario(
    scenario_name: str,
    seed: int = 42,
) -> ScenarioResult:
    """Generate an explicit seeded anomaly scenario by name.

    :param scenario_name: Name of anomaly scenario (e.g. 'NEW_DEVICE', 'MERCHANT_RISK').
    :param seed: Deterministic seed.
    :return: ScenarioResult container.
    """
    rng = random.Random(seed)
    if scenario_name == "FLAGSHIP_DEMO" or scenario_name == "V1_FLAGSHIP_DEMO_SCENARIO":
        return seeded_demo_case(seed=seed)

    generator_fn = SCENARIO_GENERATORS.get(scenario_name)
    if not generator_fn:
        available = list(SCENARIO_GENERATORS.keys()) + ["FLAGSHIP_DEMO"]
        raise ValueError(f"Unknown scenario '{scenario_name}'. Available scenarios: {available}")

    return generator_fn(rng)


__all__ = [
    "CustomerProfile",
    "MerchantProfile",
    "ScenarioResult",
    "generate_scenario",
    "generate_transactions",
    "seeded_demo_case",
]
