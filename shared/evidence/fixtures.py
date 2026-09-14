"""Fixture-backed data access for Sentinel V1 evidence tools.

Contracts v1.2 S12 states every evidence tool runs against fixture data in
V1, never a real KYC/merchant API. This module is the single place that
resolves a tool's answer from the committed scenario fixtures (data/seed/),
so shared/evidence/tools.py stays pure "validate input, call resolver,
normalize output" and never touches fixture JSON directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from shared.contracts.transaction import Geo, Transaction
from shared.detection.rules import calculate_haversine_distance_km
from shared.evidence.errors import ToolValidationError
from shared.generator.models import CustomerProfile, MerchantProfile, ScenarioResult

# A commercial flight cruises at roughly 800-900 km/h; a computed apparent
# speed above this is treated as physically implausible for a single traveler.
IMPOSSIBLE_TRAVEL_SPEED_KMH = Decimal("900.0")

# Fallback lookback window when a customer has no prior transaction history
# to compare a device/location/behavior reading against.
NO_HISTORY_LOOKBACK_HOURS = 24


@dataclass(frozen=True)
class FixtureContext:
    """Everything the fixture-backed tools may read for a single case investigation."""

    case_id: str
    transaction: Transaction
    customer: CustomerProfile
    merchant: MerchantProfile
    baseline_transactions: list[Transaction]
    secondary: CustomerProfile | None
    metadata: dict[str, object]
    known_customer_ids: set[str] = field(init=False)
    known_account_ids: dict[str, str] = field(init=False)  # account_id -> customer_id

    def __post_init__(self) -> None:
        """Derive the small known-entity index used to validate tool arguments."""
        customer_ids = {self.customer.customer_id}
        accounts = {self.customer.account_id: self.customer.customer_id}
        if self.secondary is not None:
            customer_ids.add(self.secondary.customer_id)
            accounts[self.secondary.account_id] = self.secondary.customer_id
        object.__setattr__(self, "known_customer_ids", customer_ids)
        object.__setattr__(self, "known_account_ids", accounts)


def build_fixture_context(scenario: ScenarioResult, case_id: str) -> FixtureContext:
    """Build a FixtureContext for one case investigation from a seeded scenario.

    :param scenario: Committed/generated ScenarioResult (see shared.generator.seed_loader).
    :param case_id: Case identifier this investigation belongs to.
    :return: FixtureContext the tool layer resolves calls against.
    """
    return FixtureContext(
        case_id=case_id,
        transaction=scenario.target_transaction,
        customer=scenario.customer_profile,
        merchant=scenario.merchant_profile,
        baseline_transactions=list(scenario.baseline_transactions),
        secondary=scenario.secondary_profile,
        metadata=dict(scenario.metadata),
    )


def get_failing_tool(ctx: FixtureContext) -> dict[str, object] | None:
    """Return the deliberately-configured failing tool for this case, if any.

    :param ctx: Fixture context for the active investigation.
    :return: The failing_tool metadata dict (tool_name/failure_mode/reason), or None.
    """
    failing = ctx.metadata.get("failing_tool")
    return failing if isinstance(failing, dict) else None


def _require_known_customer(ctx: FixtureContext, customer_id: str, tool_name: str) -> None:
    if customer_id not in ctx.known_customer_ids:
        raise ToolValidationError(tool_name, f"Unknown customer_id '{customer_id}' for this case")


def resolve_device_history(ctx: FixtureContext, customer_id: str, device_id: str) -> dict[str, object]:
    """Resolve get_device_history against fixture data.

    :param ctx: Fixture context for the active investigation.
    :param customer_id: Customer the device history is being checked for.
    :param device_id: Device identifier under investigation.
    :return: DeviceHistoryOutput-shaped dict, plus a "_derived" flag for Fact quality.
    """
    tool_name = "get_device_history"
    _require_known_customer(ctx, customer_id, tool_name)

    known_devices = {ctx.customer.primary_device_id}
    known_devices.update(tx.device_id for tx in ctx.baseline_transactions)

    if device_id in known_devices:
        first_seen = min(
            (tx.timestamp for tx in ctx.baseline_transactions if tx.device_id == device_id),
            default=ctx.transaction.timestamp - timedelta(days=30 * ctx.customer.tenure_months),
        )
        last_seen = max(
            (tx.timestamp for tx in ctx.baseline_transactions if tx.device_id == device_id),
            default=ctx.transaction.timestamp,
        )
        count = sum(1 for tx in ctx.baseline_transactions if tx.device_id == device_id)
        return {
            "known_device": True,
            "first_seen_at": first_seen,
            "last_seen_at": last_seen,
            "transaction_count": count,
            "device_risk_signals": [],
            "source_record_ids": [f"dvc_rec_{customer_id}_{device_id}"],
            "_derived": False,
        }

    # New/unrecognized device -- prefer an explicit committed fixture over derivation.
    explicit = ctx.metadata.get("device_history_fixture")
    if isinstance(explicit, dict) and explicit.get("device_id") == device_id:
        return {
            "known_device": explicit["known_device"],
            "first_seen_at": explicit["first_seen_at"],
            "last_seen_at": explicit["last_seen_at"],
            "transaction_count": explicit["transaction_count"],
            "device_risk_signals": explicit["device_risk_signals"],
            "source_record_ids": explicit["source_record_ids"],
            "_derived": False,
        }

    device_signals: list[dict[str, object]] = []
    device_details = ctx.metadata.get("device_details")
    if isinstance(device_details, dict) and device_details.get("device_id") == device_id:
        linkage = device_details.get("cross_account_linkage")
        if isinstance(linkage, dict):
            device_signals.append(
                {
                    "signal": "SEEN_ON_DIFFERENT_ACCOUNT",
                    "other_account_id": linkage.get("linked_account_id"),
                    "other_customer_id": linkage.get("linked_customer_id"),
                    "seen_at": (
                        ctx.transaction.timestamp
                        - timedelta(hours=float(linkage.get("seen_hours_prior", 0)))
                    ).isoformat(),
                    "hours_before_target": linkage.get("seen_hours_prior"),
                }
            )

    return {
        "known_device": False,
        "first_seen_at": ctx.transaction.timestamp,
        "last_seen_at": ctx.transaction.timestamp,
        "transaction_count": 1,
        "device_risk_signals": device_signals,
        "source_record_ids": [f"dvc_rec_{customer_id}_{device_id}"],
        "_derived": True,
    }


def resolve_linked_entities(ctx: FixtureContext, customer_id: str, account_id: str) -> dict[str, object]:
    """Resolve get_linked_entities against fixture data.

    :param ctx: Fixture context for the active investigation.
    :param customer_id: Customer initiating the linkage lookup.
    :param account_id: Account identifier being investigated for linkage.
    :return: LinkedEntitiesOutput-shaped dict, plus a "_derived" flag for Fact quality.
    """
    tool_name = "get_linked_entities"
    _require_known_customer(ctx, customer_id, tool_name)

    explicit = ctx.metadata.get("linked_entities_fixture")
    if isinstance(explicit, dict) and explicit.get("entity_id") == account_id:
        return {
            "linked_customers": explicit["linked_customers"],
            "linked_accounts": explicit["linked_accounts"],
            "recent_anomalies": explicit["recent_anomalies"],
            "relationship_signals": explicit["relationship_signals"],
            "source_record_ids": explicit["source_record_ids"],
            "_derived": False,
        }

    device_details = ctx.metadata.get("device_details")
    if isinstance(device_details, dict):
        linkage = device_details.get("cross_account_linkage")
        if isinstance(linkage, dict) and linkage.get("linked_account_id") == account_id:
            return {
                "linked_customers": [linkage.get("linked_customer_id")],
                "linked_accounts": [account_id],
                "recent_anomalies": [],
                "relationship_signals": [
                    {"signal": "SHARED_DEVICE", "device_id": device_details.get("device_id")}
                ],
                "source_record_ids": [f"lnk_rec_{account_id}"],
                "_derived": True,
            }

    if account_id in ctx.known_account_ids:
        return {
            "linked_customers": [],
            "linked_accounts": [],
            "recent_anomalies": [],
            "relationship_signals": [],
            "source_record_ids": [f"lnk_rec_{account_id}_none"],
            "_derived": True,
        }

    raise ToolValidationError(tool_name, f"Unknown account_id '{account_id}' for this case")


def resolve_ip_geovelocity(
    ctx: FixtureContext,
    customer_id: str,
    current_ip: str,
    current_geo: Geo,
    transaction_timestamp: datetime,
) -> dict[str, object]:
    """Resolve get_ip_geovelocity against fixture data.

    :param ctx: Fixture context for the active investigation.
    :param customer_id: Customer whose location history is compared against.
    :param current_ip: IP address on the transaction under investigation.
    :param current_geo: Geo coordinates on the transaction under investigation.
    :param transaction_timestamp: Timestamp of the transaction under investigation.
    :return: IpGeovelocityOutput-shaped dict, plus a "_derived" flag for Fact quality.
    """
    tool_name = "get_ip_geovelocity"
    _require_known_customer(ctx, customer_id, tool_name)
    del current_ip  # not needed for the geovelocity computation itself

    prior_transactions = [tx for tx in ctx.baseline_transactions if tx.timestamp < transaction_timestamp]
    if prior_transactions:
        previous_tx = max(prior_transactions, key=lambda tx: tx.timestamp)
        previous_geo = previous_tx.geo
        previous_timestamp = previous_tx.timestamp
        derived = False
    else:
        previous_geo = ctx.customer.home_geo
        previous_timestamp = transaction_timestamp - timedelta(hours=NO_HISTORY_LOOKBACK_HOURS)
        derived = True

    distance_km = calculate_haversine_distance_km(current_geo, previous_geo)
    elapsed_hours = Decimal(str((transaction_timestamp - previous_timestamp).total_seconds() / 3600.0))
    if elapsed_hours <= 0:
        elapsed_hours = Decimal("0.01")
    apparent_speed_kmh = distance_km / elapsed_hours

    return {
        "previous_location": {
            "lat": previous_geo.lat,
            "lon": previous_geo.lon,
            "country": previous_geo.country,
        },
        "previous_timestamp": previous_timestamp,
        "distance_km": distance_km,
        "elapsed_hours": elapsed_hours,
        "impossible_travel": apparent_speed_kmh > IMPOSSIBLE_TRAVEL_SPEED_KMH,
        "source_record_ids": [f"geo_rec_{customer_id}"],
        "_derived": derived,
    }


def resolve_behavioral_baseline(
    ctx: FixtureContext,
    customer_id: str,
    transaction: Transaction,
) -> dict[str, object]:
    """Resolve get_behavioral_baseline against fixture data.

    :param ctx: Fixture context for the active investigation.
    :param customer_id: Customer whose spending baseline is compared against.
    :param transaction: Transaction under investigation.
    :return: BehavioralBaselineOutput-shaped dict, plus a "_derived" flag for Fact quality.
    """
    tool_name = "get_behavioral_baseline"
    _require_known_customer(ctx, customer_id, tool_name)

    typical_amount = ctx.customer.typical_amount_mean
    std = ctx.customer.typical_amount_std
    amount_deviation = (
        abs(transaction.amount - typical_amount) / std if std > 0 else abs(transaction.amount - typical_amount)
    )

    hours = [tx.timestamp.hour for tx in ctx.baseline_transactions]
    if hours:
        mean_hour = sum(hours) / len(hours)
        variance = sum((h - mean_hour) ** 2 for h in hours) / len(hours)
        std_hours = variance**0.5
        derived = False
    else:
        mean_hour = float(transaction.timestamp.hour)
        std_hours = 0.0
        derived = True

    hour_gap = abs(transaction.timestamp.hour - mean_hour)
    time_deviation = Decimal(str(min(hour_gap, 24 - hour_gap)))

    return {
        "typical_amount": typical_amount,
        "amount_deviation": amount_deviation,
        "typical_hours": {"mean_hour": mean_hour, "std_hours": std_hours},
        "time_deviation": time_deviation,
        "historical_transaction_count": len(ctx.baseline_transactions),
        "source_record_ids": [f"bhv_rec_{customer_id}"],
        "_derived": derived,
    }


def resolve_merchant_risk(ctx: FixtureContext, merchant_id: str, customer_id: str) -> dict[str, object]:
    """Resolve get_merchant_risk against fixture data.

    :param ctx: Fixture context for the active investigation.
    :param merchant_id: Merchant under investigation.
    :param customer_id: Customer transacting with the merchant.
    :return: MerchantRiskOutput-shaped dict, plus a "_derived" flag for Fact quality.
    """
    tool_name = "get_merchant_risk"
    _require_known_customer(ctx, customer_id, tool_name)
    if merchant_id != ctx.merchant.merchant_id:
        raise ToolValidationError(tool_name, f"Unknown merchant_id '{merchant_id}' for this case")

    prior_count = sum(1 for tx in ctx.baseline_transactions if tx.merchant_id == merchant_id)

    return {
        "category": ctx.merchant.category,
        "onboarding_date": ctx.merchant.onboarding_date,
        "chargeback_rate": ctx.merchant.chargeback_rate,
        "recent_fraud_report_count": ctx.merchant.recent_fraud_report_count,
        "fraud_report_trend": ctx.merchant.fraud_report_trend,
        "customer_prior_transactions_with_merchant": prior_count,
        "risk_band": ctx.merchant.risk_band,
        "_derived": False,
    }


def resolve_mock_kyc_status(ctx: FixtureContext, customer_id: str) -> dict[str, object]:
    """Resolve get_mock_kyc_status against fixture data.

    :param ctx: Fixture context for the active investigation.
    :param customer_id: Customer whose KYC status is being checked.
    :return: MockKycOutput-shaped dict, plus a "_derived" flag for Fact quality.
    """
    tool_name = "get_mock_kyc_status"
    _require_known_customer(ctx, customer_id, tool_name)

    profile = ctx.customer if customer_id == ctx.customer.customer_id else ctx.secondary
    assert profile is not None  # guaranteed by _require_known_customer
    status = profile.kyc_status
    flags = [] if status == "VERIFIED" else [f"KYC_STATUS_{status}"]

    return {
        "kyc_status": status,
        "kyc_flags": flags,
        "source_record_ids": [f"kyc_rec_{customer_id}"],
        "_derived": False,
    }
