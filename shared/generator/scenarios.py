"""Deterministic seeded anomaly and flagship demo scenarios for Sentinel V1."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import random

from shared.contracts.detection import RiskBand
from shared.contracts.tools import FraudReportTrend
from shared.contracts.transaction import Channel, Geo, Transaction
from shared.generator.models import CustomerProfile, MerchantProfile, ScenarioResult
from shared.generator.profiles import CITIES, create_customer_profile, create_merchant_profile
from shared.generator.transactions import generate_normal_transactions, generate_single_transaction


def generate_new_device_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a scenario where a transaction is attempted from an unrecognized device."""
    customer = create_customer_profile("cust_sc_newdev", rng, city_idx=0)
    merchant = create_merchant_profile("merch_standard_01")
    baseline = generate_normal_transactions(customer, [merchant], count=10, rng=rng)

    target_time = baseline[-1].timestamp + timedelta(hours=12)
    unseen_device_id = f"dev_unseen_{rng.randint(80000, 99999)}"

    target_tx = generate_single_transaction(
        transaction_id="tx_sc_new_device",
        customer=customer,
        merchant=merchant,
        amount=Decimal("120.00"),
        timestamp=target_time,
        device_id=unseen_device_id,
    )

    return ScenarioResult(
        scenario_name="NEW_DEVICE",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        metadata={
            "seeded_anomaly": "NEW_DEVICE",
            "primary_device": customer.primary_device_id,
            "used_device": unseen_device_id,
        },
    )


def generate_unusual_location_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a scenario where transaction originates from an atypical geography."""
    customer = create_customer_profile("cust_sc_loc", rng, city_idx=0)  # New York
    merchant = create_merchant_profile("merch_standard_02")
    baseline = generate_normal_transactions(customer, [merchant], count=10, rng=rng)

    target_time = baseline[-1].timestamp + timedelta(days=2)
    unusual_city = CITIES[2]  # London
    unusual_geo = Geo(lat=unusual_city[0], lon=unusual_city[1], country=unusual_city[2])

    target_tx = generate_single_transaction(
        transaction_id="tx_sc_unusual_loc",
        customer=customer,
        merchant=merchant,
        amount=Decimal("85.00"),
        timestamp=target_time,
        ip_address="82.165.197.1",
        geo=unusual_geo,
    )

    return ScenarioResult(
        scenario_name="UNUSUAL_LOCATION",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        metadata={
            "seeded_anomaly": "UNUSUAL_LOCATION",
            "home_country": customer.home_geo.country,
            "transaction_country": unusual_geo.country,
        },
    )


def generate_unusual_amount_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a scenario where transaction amount drastically exceeds historical baseline."""
    customer = create_customer_profile(
        "cust_sc_amt",
        rng,
        mean_amount=Decimal("45.00"),
        std_amount=Decimal("15.00"),
    )
    merchant = create_merchant_profile("merch_luxury_01", category="retail_apparel")
    baseline = generate_normal_transactions(customer, [merchant], count=15, rng=rng)

    target_time = baseline[-1].timestamp + timedelta(hours=8)
    unusual_amount = Decimal("2499.99")  # Many standard deviations above mean

    target_tx = generate_single_transaction(
        transaction_id="tx_sc_unusual_amount",
        customer=customer,
        merchant=merchant,
        amount=unusual_amount,
        timestamp=target_time,
    )

    return ScenarioResult(
        scenario_name="UNUSUAL_AMOUNT",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        metadata={
            "seeded_anomaly": "UNUSUAL_AMOUNT",
            "historical_mean": str(customer.typical_amount_mean),
            "target_amount": str(unusual_amount),
        },
    )


def generate_unusual_time_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a scenario where transaction occurs during atypical customer hours (e.g. 03:30 AM)."""
    customer = create_customer_profile("cust_sc_time", rng)
    merchant = create_merchant_profile("merch_gaming_01", category="entertainment")
    baseline = generate_normal_transactions(customer, [merchant], count=10, rng=rng)

    # Force timestamp to 03:35:00 UTC (deep night anomaly)
    last_date = baseline[-1].timestamp.date() + timedelta(days=1)
    unusual_timestamp = datetime(last_date.year, last_date.month, last_date.day, 3, 35, 0, tzinfo=timezone.utc)

    target_tx = generate_single_transaction(
        transaction_id="tx_sc_unusual_time",
        customer=customer,
        merchant=merchant,
        amount=Decimal("60.00"),
        timestamp=unusual_timestamp,
    )

    return ScenarioResult(
        scenario_name="UNUSUAL_TIME",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        metadata={
            "seeded_anomaly": "UNUSUAL_TIME",
            "target_hour_utc": 3,
        },
    )


def generate_impossible_travel_scenario(rng: random.Random) -> ScenarioResult:
    """Generate an impossible travel scenario (NYC at 12:00, Tokyo 45 minutes later)."""
    customer = create_customer_profile("cust_sc_speed", rng, city_idx=0)  # NYC
    merchant = create_merchant_profile("merch_travel_01", category="digital_goods")
    baseline = generate_normal_transactions(customer, [merchant], count=8, rng=rng)

    # Previous transaction in NYC at 12:00 UTC
    tx_time_1 = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    nyc_tx = generate_single_transaction(
        transaction_id="tx_prior_nyc",
        customer=customer,
        merchant=merchant,
        amount=Decimal("25.00"),
        timestamp=tx_time_1,
        geo=customer.home_geo,
    )
    baseline.append(nyc_tx)

    # 45 minutes later in Tokyo (10,800 km away -> > 14,000 km/h)
    tx_time_2 = tx_time_1 + timedelta(minutes=45)
    tokyo_city = CITIES[3]  # Tokyo
    tokyo_geo = Geo(lat=tokyo_city[0], lon=tokyo_city[1], country=tokyo_city[2])

    target_tx = generate_single_transaction(
        transaction_id="tx_sc_impossible_travel",
        customer=customer,
        merchant=merchant,
        amount=Decimal("450.00"),
        timestamp=tx_time_2,
        ip_address="133.242.0.1",
        geo=tokyo_geo,
    )

    return ScenarioResult(
        scenario_name="IMPOSSIBLE_TRAVEL",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        metadata={
            "seeded_anomaly": "IMPOSSIBLE_TRAVEL",
            "prior_tx_time": tx_time_1.isoformat(),
            "target_tx_time": tx_time_2.isoformat(),
            "distance_km_approx": 10800,
            "elapsed_minutes": 45,
        },
    )


def generate_merchant_risk_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a transaction with a high-risk merchant exhibiting rising chargebacks."""
    customer = create_customer_profile("cust_sc_mrisk", rng)
    risky_merchant = create_merchant_profile(
        merchant_id="merch_risky_electronics",
        category="electronics",
        risk_band=RiskBand.HIGH,
        chargeback_rate=Decimal("0.042"),
        recent_fraud_reports=6,
        fraud_trend=FraudReportTrend.RISING,
        onboarding_date=date(2025, 3, 1),
    )
    baseline = generate_normal_transactions(customer, [risky_merchant], count=5, rng=rng)

    target_time = baseline[-1].timestamp + timedelta(hours=18)
    target_tx = generate_single_transaction(
        transaction_id="tx_sc_merchant_risk",
        customer=customer,
        merchant=risky_merchant,
        amount=Decimal("380.00"),
        timestamp=target_time,
    )

    return ScenarioResult(
        scenario_name="MERCHANT_RISK",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=risky_merchant,
        metadata={
            "seeded_anomaly": "MERCHANT_RISK",
            "chargeback_rate": str(risky_merchant.chargeback_rate),
            "fraud_trend": risky_merchant.fraud_report_trend.value,
        },
    )


def generate_linked_entity_anomaly_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a scenario where customer's account is linked to an account flagged for fraud."""
    customer = create_customer_profile("cust_sc_link_01", rng)
    secondary_cust = create_customer_profile("cust_sc_flagged_02", rng, kyc_status="REVIEW")

    customer.linked_account_ids = [secondary_cust.account_id]
    merchant = create_merchant_profile("merch_general_01")
    baseline = generate_normal_transactions(customer, [merchant], count=6, rng=rng)

    target_time = baseline[-1].timestamp + timedelta(hours=14)
    target_tx = generate_single_transaction(
        transaction_id="tx_sc_linked_entity",
        customer=customer,
        merchant=merchant,
        amount=Decimal("199.00"),
        timestamp=target_time,
    )

    return ScenarioResult(
        scenario_name="LINKED_ENTITY_ANOMALY",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        secondary_profile=secondary_cust,
        metadata={
            "seeded_anomaly": "LINKED_ENTITY_ANOMALY",
            "linked_account_id": secondary_cust.account_id,
            "linked_customer_status": secondary_cust.kyc_status,
        },
    )


def generate_kyc_anomaly_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a transaction for a customer whose KYC verification has failed."""
    customer = create_customer_profile("cust_sc_kyc_failed", rng, kyc_status="FAILED")
    merchant = create_merchant_profile("merch_electronics_01")
    baseline = generate_normal_transactions(customer, [merchant], count=4, rng=rng)

    target_time = baseline[-1].timestamp + timedelta(hours=10)
    target_tx = generate_single_transaction(
        transaction_id="tx_sc_kyc_anomaly",
        customer=customer,
        merchant=merchant,
        amount=Decimal("95.00"),
        timestamp=target_time,
    )

    return ScenarioResult(
        scenario_name="KYC_ANOMALY",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        metadata={
            "seeded_anomaly": "KYC_ANOMALY",
            "kyc_status": customer.kyc_status,
        },
    )


def generate_clean_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a fully clean/normal transaction that triggers zero anomaly tags.

    Known device, home location, typical amount, low-risk merchant, verified KYC,
    no linked accounts -- intended to AUTO_RESOLVE with an empty evidence
    investigation (Contracts v1.2 Policy rule P-005).
    """
    customer = create_customer_profile("cust_sc_clean", rng, city_idx=1)
    merchant = create_merchant_profile("merch_standard_clean")
    baseline = generate_normal_transactions(customer, [merchant], count=8, rng=rng)

    target_time = baseline[-1].timestamp + timedelta(hours=10)
    target_tx = generate_single_transaction(
        transaction_id="tx_sc_clean_normal",
        customer=customer,
        merchant=merchant,
        amount=customer.typical_amount_mean,
        timestamp=target_time,
    )

    return ScenarioResult(
        scenario_name="CLEAN_NORMAL",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        metadata={
            "seeded_anomaly": "NONE",
            "expected_anomaly_tags": [],
            "expected_policy_outcome": "AUTO_RESOLVE",
        },
    )


def generate_branching_proof_scenario(rng: random.Random) -> ScenarioResult:
    """Generate the branching-proof scenario: ONLY NEW_DEVICE fires at detection time.

    Seeds get_device_history / get_linked_entities fixture data (for the Phase 2
    Evidence Agent) showing this device was also seen on a *different* account 2
    hours earlier, and that the linked account carries a recent anomaly -- a
    relationship the agent must discover and choose to follow on its own.

    Nothing in the minimum-evidence floor for NEW_DEVICE alone (Contracts v1.2
    S11.4: NEW_DEVICE -> get_device_history only) requires calling
    get_linked_entities, so any such call is genuine agentic branching, not a
    fixed-mapping artifact.
    """
    customer = create_customer_profile("cust_sc_branch_primary", rng, city_idx=0)
    merchant = create_merchant_profile("merch_standard_branch")
    baseline = generate_normal_transactions(customer, [merchant], count=10, rng=rng)

    # Secondary/linked customer whose account the shared device also touched.
    secondary_customer = create_customer_profile(
        "cust_sc_branch_secondary", rng, city_idx=4, kyc_status="REVIEW"
    )

    target_time = baseline[-1].timestamp + timedelta(hours=6)
    shared_device_id = f"dev_branch_shared_{rng.randint(70000, 79999)}"
    device_seen_on_secondary = target_time - timedelta(hours=2)

    target_tx = generate_single_transaction(
        transaction_id="tx_sc_branching_proof",
        customer=customer,
        merchant=merchant,
        amount=customer.typical_amount_mean,
        timestamp=target_time,
        device_id=shared_device_id,
    )

    return ScenarioResult(
        scenario_name="BRANCHING_PROOF",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        secondary_profile=secondary_customer,
        metadata={
            "seeded_anomaly": "NEW_DEVICE",
            "expected_anomaly_tags": ["NEW_DEVICE"],
            "expected_policy_outcome": "ESCALATE",
            "minimum_evidence_floor_for_new_device": ["get_device_history"],
            "floor_requires_get_linked_entities": False,
            "branching_hook_note": (
                "The agent must discover the cross-account device link on its own by "
                "inspecting get_device_history's result and choosing to call "
                "get_linked_entities -- the NEW_DEVICE floor alone never requires it."
            ),
            "device_history_fixture": {
                "device_id": shared_device_id,
                "customer_id": customer.customer_id,
                "known_device": False,
                "first_seen_at": device_seen_on_secondary.isoformat(),
                "last_seen_at": target_time.isoformat(),
                "transaction_count": 1,
                "device_risk_signals": [
                    {
                        "signal": "SEEN_ON_DIFFERENT_ACCOUNT",
                        "other_account_id": secondary_customer.account_id,
                        "other_customer_id": secondary_customer.customer_id,
                        "seen_at": device_seen_on_secondary.isoformat(),
                        "hours_before_target": 2,
                    }
                ],
                "source_record_ids": ["dvc_rec_branch_001"],
            },
            "linked_entities_fixture": {
                "entity_id": secondary_customer.account_id,
                "relation_scope": "DEVICE_LINKED",
                "linked_customers": [secondary_customer.customer_id],
                "linked_accounts": [secondary_customer.account_id],
                "recent_anomalies": [
                    {
                        "anomaly_type": "KYC_STATUS_REVIEW",
                        "account_id": secondary_customer.account_id,
                        "observed_at": (target_time - timedelta(hours=5)).isoformat(),
                        "detail": f"Account {secondary_customer.account_id} KYC status is REVIEW",
                    }
                ],
                "relationship_signals": [
                    {"signal": "SHARED_DEVICE", "device_id": shared_device_id}
                ],
                "source_record_ids": ["lnk_rec_branch_001"],
            },
        },
    )


def generate_partial_evidence_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a scenario where the single tool the evidence floor requires is
    deliberately configured to fail/timeout, proving the fail-safe escalation path.

    NEW_DEVICE fires (floor requires only get_device_history); get_device_history
    itself is marked as failing in metadata, so the minimum-evidence floor can never
    be satisfied and the case must fail safe to PARTIAL evidence / ESCALATE
    (Contracts v1.2 S14, Policy rule P-001).
    """
    customer = create_customer_profile("cust_sc_partial", rng, city_idx=2)
    merchant = create_merchant_profile("merch_standard_partial")
    baseline = generate_normal_transactions(customer, [merchant], count=8, rng=rng)

    target_time = baseline[-1].timestamp + timedelta(hours=9)
    unseen_device_id = f"dev_partial_unseen_{rng.randint(60000, 69999)}"

    target_tx = generate_single_transaction(
        transaction_id="tx_sc_partial_evidence",
        customer=customer,
        merchant=merchant,
        amount=customer.typical_amount_mean,
        timestamp=target_time,
        device_id=unseen_device_id,
    )

    return ScenarioResult(
        scenario_name="PARTIAL_EVIDENCE",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=merchant,
        metadata={
            "seeded_anomaly": "NEW_DEVICE",
            "expected_anomaly_tags": ["NEW_DEVICE"],
            "expected_evidence_completeness": "PARTIAL",
            "expected_policy_outcome": "ESCALATE",
            "failing_tool": {
                "tool_name": "get_device_history",
                "failure_mode": "TIMEOUT",
                "reason": (
                    "Deliberately configured to fail so the NEW_DEVICE minimum-evidence "
                    "floor (get_device_history) can never be satisfied, proving the "
                    "fail-safe escalation path per Contracts v1.2 S14 / Policy rule P-001."
                ),
            },
        },
    )


def generate_merchant_risk_trend_scenario(rng: random.Random) -> ScenarioResult:
    """Generate a single-signal MERCHANT_RISK scenario at a genuinely new-to-customer
    merchant with a rising fraud-report trend, used for the Decision Robustness
    Scorer demo variant (Phase 3).

    Unlike the multi-signal flagship demo, this case isolates MERCHANT_RISK as the
    sole anomaly signal so a live counterfactual (remove the merchant-risk factor)
    has a clean, unambiguous chance of flipping the outcome to FRAGILE.
    """
    customer = create_customer_profile("cust_sc_mrtrend", rng, city_idx=3)
    familiar_merchant = create_merchant_profile("merch_familiar_groceries", category="groceries")
    baseline = generate_normal_transactions(customer, [familiar_merchant], count=6, rng=rng)

    risky_new_merchant = create_merchant_profile(
        merchant_id="merch_risky_new_electronics",
        category="electronics",
        risk_band=RiskBand.HIGH,
        chargeback_rate=Decimal("0.035"),
        recent_fraud_reports=4,
        fraud_trend=FraudReportTrend.RISING,
        onboarding_date=date(2025, 6, 1),
    )

    target_time = baseline[-1].timestamp + timedelta(hours=20)
    target_tx = generate_single_transaction(
        transaction_id="tx_sc_merchant_risk_trend",
        customer=customer,
        merchant=risky_new_merchant,
        amount=customer.typical_amount_mean,
        timestamp=target_time,
    )

    return ScenarioResult(
        scenario_name="MERCHANT_RISK_TREND",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=customer,
        merchant_profile=risky_new_merchant,
        metadata={
            "seeded_anomaly": "MERCHANT_RISK",
            "expected_anomaly_tags": ["MERCHANT_RISK"],
            "expected_policy_outcome": "ESCALATE",
            "customer_prior_transactions_with_merchant": 0,
            "fraud_report_trend": risky_new_merchant.fraud_report_trend.value,
            "recent_fraud_report_count": risky_new_merchant.recent_fraud_report_count,
            "robustness_demo_note": (
                "Single-signal MERCHANT_RISK case intended for the Decision Robustness "
                "Scorer demo variant: removing the sole HIGH-materiality merchant-risk "
                "factor is expected to flip the case to FRAGILE (Phase 3)."
            ),
        },
    )


def seeded_demo_case(seed: int = 42) -> ScenarioResult:
    """Generate the authoritative V1.1 Flagship Demo Scenario.

    Dimensions:
    - Customer: 18-month established tenure with normal baseline transactions.
    - Card: Primary card, card_present = false.
    - Anomaly tags: NEW_DEVICE, UNUSUAL_LOCATION, MERCHANT_RISK.
    - Branching hook: Device (dev_demo_suspicious) first seen 40 minutes prior,
      and was ALSO seen 2 hours earlier on secondary account acc_compromised_02!
    - Merchant: High risk, chargeback rate > 2%, 3 reports in last 30 days, rising trend.
    - Location: Unusual location (Miami vs established New York home).

    :param seed: Deterministic seed.
    :return: ScenarioResult container.
    """
    rng = random.Random(seed)

    # 1. Primary Customer Profile (18-month tenure in New York)
    primary_customer = create_customer_profile(
        customer_id="cust_demo_established_01",
        rng=rng,
        city_idx=0,  # New York
        tenure_months=18,
        mean_amount=Decimal("85.00"),
        std_amount=Decimal("20.00"),
    )

    # 2. Secondary Customer / Account for cross-account branching
    secondary_customer = create_customer_profile(
        customer_id="cust_demo_compromised_02",
        rng=rng,
        city_idx=4,  # Chicago
        tenure_months=6,
    )
    primary_customer.linked_account_ids = [secondary_customer.account_id]

    # 3. High Risk Merchant with rising fraud report trend
    merchant = create_merchant_profile(
        merchant_id="merch_demo_electronics_risky",
        category="electronics",
        risk_band=RiskBand.HIGH,
        chargeback_rate=Decimal("0.028"),
        recent_fraud_reports=3,
        fraud_trend=FraudReportTrend.RISING,
        onboarding_date=date(2025, 2, 10),
    )

    # 4. Standard Merchants for Baseline
    merch_groceries = create_merchant_profile("merch_demo_groceries", category="groceries")
    merch_apparel = create_merchant_profile("merch_demo_apparel", category="retail_apparel")
    baseline = generate_normal_transactions(
        primary_customer,
        [merch_groceries, merch_apparel],
        count=12,
        rng=rng,
        base_time=datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc),
    )

    # 5. Target Transaction Details
    # Timestamp: 2026-09-13 14:00:00 UTC
    target_time = datetime(2026, 9, 13, 14, 0, 0, tzinfo=timezone.utc)

    # Suspicious Device first seen 40 minutes before transaction
    suspicious_device_id = "dev_demo_suspicious_99"

    # Unusual Location: Miami (customer is established in New York)
    miami_city = CITIES[5]  # Miami
    unusual_geo = Geo(lat=miami_city[0], lon=miami_city[1], country=miami_city[2])

    target_tx = generate_single_transaction(
        transaction_id="tx_demo_v1_flagship",
        customer=primary_customer,
        merchant=merchant,
        amount=Decimal("499.99"),
        timestamp=target_time,
        device_id=suspicious_device_id,
        ip_address="198.51.100.88",
        geo=unusual_geo,
        channel=Channel.WEB,
    )

    return ScenarioResult(
        scenario_name="V1_FLAGSHIP_DEMO_SCENARIO",
        target_transaction=target_tx,
        baseline_transactions=baseline,
        customer_profile=primary_customer,
        merchant_profile=merchant,
        secondary_profile=secondary_customer,
        metadata={
            "scenario": "FLAGSHIP_CNP_ECOMMERCE_PRE_AUTH",
            "intended_anomaly_tags": [
                "NEW_DEVICE",
                "UNUSUAL_LOCATION",
                "MERCHANT_RISK",
            ],
            "device_details": {
                "device_id": suspicious_device_id,
                "first_seen_minutes_prior": 40,
                "cross_account_linkage": {
                    "linked_customer_id": secondary_customer.customer_id,
                    "linked_account_id": secondary_customer.account_id,
                    "seen_hours_prior": 2,
                },
            },
            "location_details": {
                "established_home_city": "New York, USA",
                "transaction_city": "Miami, USA",
                "anomaly_type": "UNUSUAL_LOCATION",
            },
            "merchant_details": {
                "merchant_id": merchant.merchant_id,
                "recent_fraud_report_count": 3,
                "fraud_report_trend": "RISING",
                "customer_prior_transactions_with_merchant": 0,
                "risk_band": "HIGH",
            },
            "branching_hook_note": (
                "get_device_history(dev_demo_suspicious_99) reveals association with "
                f"{secondary_customer.account_id} 2 hours earlier, prompting Evidence Agent "
                "to branch to get_linked_entities."
            ),
        },
    )
