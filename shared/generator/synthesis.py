"""Deterministic synthetic investigation context for transactions that match
no committed seed fixture (build.md: "unknown transaction != automatic
fraud").

Architecture (confirmed before implementation -- see project history):
customer/merchant baselines are a STABLE function of identity alone
(customer_id+account_id+card_id / merchant_id respectively) -- they are
computed once per identity and never regenerated to match whatever
transaction happens to be under investigation. The real submitted
transaction is then compared against that stable baseline by the existing,
unmodified Detection/Evidence/Reasoning/Robustness/Policy pipeline. Two
different transactions from the same customer identity get byte-identical
baselines; whether either one looks "normal" depends entirely on whether
its own fields happen to match that fixed baseline -- exactly like a real
customer's own transactions naturally match their own real history, while
someone else's don't.

This reuses the same generator primitives (shared/generator/profiles.py,
transactions.py) that originally produced every committed scenario fixture
under data/seed/ -- this is not a new data source or a new architecture, it
is the already-in-scope V1 synthetic transaction generator (Architecture
"Build (V1)" list) invoked at request time instead of only at fixture-export
time.

No hidden risk mapping: no function in this module ever receives or derives
an "intended" LOW/MEDIUM/HIGH/clean/fraud outcome. Every derivation reads
only identity fields (customer_id/account_id/card_id, merchant_id) via
hashlib.sha256 -- never amount, never device/geo VALUES, never a risk flag.
scripts/show_synthetic_customer_baseline.py exposes exactly what this module
computes, read-only and offline, so a transaction document can be authored
to genuinely match (or deliberately deviate from) a real computed baseline --
that is data authoring, not an outcome mapping inside the system.
"""

from __future__ import annotations

import hashlib
import random
from datetime import timedelta
from decimal import Decimal

from shared.contracts.detection import RiskBand
from shared.contracts.tools import FraudReportTrend
from shared.contracts.transaction import Transaction
from shared.generator.models import CustomerProfile, MerchantProfile, ScenarioResult
from shared.generator.profiles import CITIES, MERCHANT_CATEGORIES, create_customer_profile, create_merchant_profile
from shared.generator.transactions import generate_normal_transactions

BASELINE_TRANSACTION_COUNT = 8
KNOWN_DEVICES_PER_CUSTOMER = 2
LINKED_ENTITY_PROBABILITY_PERCENT = 15

# Baseline transactions are generated forward from this many days before the
# submitted transaction's own timestamp. generate_normal_transactions spaces
# entries 6-36 hours apart, so BASELINE_TRANSACTION_COUNT * 36h (~12 days)
# is the worst case -- 45 days leaves a comfortable margin so every
# synthesized baseline entry is guaranteed to predate the real transaction,
# without needing a fragile post-hoc filter.
BASELINE_LOOKBACK_DAYS = 45


def _stable_seed(*parts: str) -> int:
    """Derive a stable integer seed from identifier strings.

    Uses hashlib.sha256, not Python's built-in hash() (which is
    process-randomized for str/bytes unless PYTHONHASHSEED is fixed) --
    the same parts always produce the same seed, in any process.
    """
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def derive_customer_baseline(customer_id: str, account_id: str, card_id: str) -> tuple[CustomerProfile, list[str]]:
    """Deterministically derive a customer's STABLE baseline -- a pure
    function of identity alone, never of any specific transaction. The same
    (customer_id, account_id, card_id) always returns byte-identical
    results, regardless of which transaction is being investigated.

    :param customer_id: The transaction's customer_id.
    :param account_id: The transaction's account_id.
    :param card_id: The transaction's card_id.
    :return: (CustomerProfile with primary_device_id set to the first known
        device, the full list of this customer's known device IDs --
        generate_normal_transactions rotates baseline history across all of
        them, so "known device" naturally covers more than a single value).
    """
    seed = _stable_seed("customer", customer_id, account_id, card_id)
    rng = random.Random(seed)

    known_devices = [f"dev_{seed % 1_000_000:06d}_{i}" for i in range(1, KNOWN_DEVICES_PER_CUSTOMER + 1)]

    customer = create_customer_profile(
        customer_id=customer_id,
        rng=rng,
        city_idx=seed % len(CITIES),
        tenure_months=3 + (seed % 46),
        mean_amount=Decimal(str(40 + (seed % 111))),
        std_amount=Decimal(str(10 + (seed % 31))),
        kyc_status="VERIFIED",  # no real KYC signal to derive from an uploaded transaction
    )
    customer = customer.model_copy(
        update={"account_id": account_id, "card_id": card_id, "primary_device_id": known_devices[0]}
    )
    return customer, known_devices


def _derive_merchant_risk_posture(seed: int) -> tuple[RiskBand, Decimal, FraudReportTrend, int]:
    """Deterministically derive a merchant's risk posture from its own
    merchant_id -- a stable fact about that merchant, shared by every
    customer who transacts with it. This can legitimately produce a
    HIGH-risk profile (letting a real MERCHANT_RISK anomaly fire honestly),
    but only as a consequence of which merchant_id was submitted, never as
    a function of amount, customer, or any attempt to force an outcome."""
    band_roll = seed % 1000
    if band_roll < 200:  # ~20% of synthetic merchants are genuinely high-risk
        return (
            RiskBand.HIGH,
            Decimal(str(round(0.025 + (band_roll % 36) / 1000, 3))),
            FraudReportTrend.RISING,
            2 + (band_roll % 7),
        )
    if band_roll < 500:  # ~30% medium
        return (
            RiskBand.MEDIUM,
            Decimal(str(round(0.008 + (band_roll % 13) / 1000, 3))),
            FraudReportTrend.STABLE,
            band_roll % 3,
        )
    return (  # ~50% low
        RiskBand.LOW,
        Decimal(str(round(0.001 + (band_roll % 8) / 1000, 3))),
        FraudReportTrend.STABLE,
        0,
    )


def derive_merchant_profile(merchant_id: str) -> MerchantProfile:
    """Deterministically derive a merchant's STABLE profile from merchant_id
    alone -- shared by every customer who transacts with this merchant,
    never derived from any specific transaction's amount, customer, or any
    notion of intended risk.

    :param merchant_id: The transaction's merchant_id.
    :return: A MerchantProfile; the same merchant_id always returns a
        byte-identical result.
    """
    seed = _stable_seed("merchant", merchant_id)
    category = MERCHANT_CATEGORIES[seed % len(MERCHANT_CATEGORIES)]
    risk_band, chargeback_rate, fraud_trend, recent_fraud_reports = _derive_merchant_risk_posture(seed)
    return create_merchant_profile(
        merchant_id=merchant_id,
        category=category,
        risk_band=risk_band,
        chargeback_rate=chargeback_rate,
        recent_fraud_reports=recent_fraud_reports,
        fraud_trend=fraud_trend,
    )


def derive_linked_entity(customer_id: str, account_id: str, card_id: str) -> CustomerProfile | None:
    """Deterministically decide whether this customer identity has a
    genuinely linked secondary entity with an anomalous KYC status --
    purely from identity (never from the transaction under investigation,
    never from an intended outcome). ~15% of customer identities get one,
    so LINKED_ENTITY_ANOMALY remains reachable without ever being
    fabricated for a specific transaction.

    :return: A secondary CustomerProfile (KYC status REVIEW), or None.
    """
    seed = _stable_seed("linked", customer_id, account_id, card_id)
    if seed % 100 >= LINKED_ENTITY_PROBABILITY_PERCENT:
        return None
    secondary_seed = _stable_seed("linked_secondary", customer_id, account_id, card_id)
    return create_customer_profile(
        customer_id=f"{customer_id}_linked",
        rng=random.Random(secondary_seed),
        city_idx=secondary_seed % len(CITIES),
        kyc_status="REVIEW",
    )


def synthesize_scenario_for_transaction(transaction: Transaction) -> ScenarioResult:
    """Build the investigation context for a transaction that matches no
    committed seed fixture: a stable, identity-derived customer/merchant
    baseline, plus the real submitted transaction to be compared against it
    by the unmodified pipeline.

    :param transaction: The real, submitted Transaction -- used verbatim as
        the scenario's target_transaction, never replaced or altered, and
        never itself used to derive the baseline it will be compared against.
    :return: A ScenarioResult the existing pipeline (Detection through
        Policy) investigates exactly as it would a committed fixture.
    """
    customer, known_devices = derive_customer_baseline(
        transaction.customer_id, transaction.account_id, transaction.card_id
    )
    merchant = derive_merchant_profile(transaction.merchant_id)

    secondary = derive_linked_entity(transaction.customer_id, transaction.account_id, transaction.card_id)
    if secondary is not None:
        customer = customer.model_copy(update={"linked_account_ids": [secondary.account_id]})

    baseline_seed = _stable_seed("baseline", transaction.customer_id, transaction.account_id, transaction.card_id)
    base_time = transaction.timestamp - timedelta(days=BASELINE_LOOKBACK_DAYS)
    baseline_transactions = generate_normal_transactions(
        customer,
        [merchant],
        count=BASELINE_TRANSACTION_COUNT,
        rng=random.Random(baseline_seed),
        base_time=base_time,
        device_pool=known_devices,
    )

    return ScenarioResult(
        scenario_name="SYNTHETIC_UNKNOWN_TRANSACTION",
        target_transaction=transaction,
        baseline_transactions=baseline_transactions,
        customer_profile=customer,
        merchant_profile=merchant,
        secondary_profile=secondary,
        metadata={
            "synthetic": True,
            "synthetic_note": (
                "This transaction matched no committed seed fixture. The customer/merchant "
                "baseline is a stable function of identity alone (customer_id/account_id/card_id, "
                "merchant_id) -- it is demo/prototype data, not a connection to any real banking, "
                "customer, or merchant system, and it is never regenerated to match this specific "
                "transaction. Detection, Evidence Agent, Reasoning, Robustness, and Policy all ran "
                "unmodified, comparing the real submitted transaction against this baseline."
            ),
        },
    )
