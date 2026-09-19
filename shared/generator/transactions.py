"""Deterministic transaction generation conforming strictly to Sentinel V1 contracts."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import random

from shared.contracts.transaction import (
    AuthorizationStage,
    Channel,
    Direction,
    Geo,
    PaymentRail,
    Transaction,
)
from shared.generator.models import CustomerProfile, MerchantProfile


def generate_single_transaction(
    transaction_id: str,
    customer: CustomerProfile,
    merchant: MerchantProfile,
    amount: Decimal,
    timestamp: datetime,
    device_id: str | None = None,
    ip_address: str | None = None,
    geo: Geo | None = None,
    channel: Channel = Channel.WEB,
) -> Transaction:
    """Construct a valid V1 Transaction instance from profile and override data.

    :param transaction_id: Unique identifier for transaction.
    :param customer: CustomerProfile providing customer, account, and card IDs.
    :param merchant: MerchantProfile providing merchant details and category.
    :param amount: Monetary amount.
    :param timestamp: UTC timestamp of transaction.
    :param device_id: Override device ID or defaults to customer's primary device.
    :param ip_address: Override IP or defaults to customer's primary IP.
    :param geo: Override location or defaults to customer's home geo.
    :param channel: Channel (WEB or MOBILE).
    :return: Validated V1 Transaction.
    """
    clean_amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return Transaction(
        transaction_id=transaction_id,
        customer_id=customer.customer_id,
        account_id=customer.account_id,
        card_id=customer.card_id,
        merchant_id=merchant.merchant_id,
        amount=clean_amount,
        currency="USD",
        timestamp=timestamp,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id=device_id or customer.primary_device_id,
        ip_address=ip_address or customer.primary_ip,
        geo=geo or customer.home_geo,
        channel=channel,
        merchant_category=merchant.category,
        card_present=False,
    )


def generate_normal_transactions(
    customer: CustomerProfile,
    merchants: list[MerchantProfile],
    count: int,
    rng: random.Random,
    base_time: datetime | None = None,
    device_pool: list[str] | None = None,
) -> list[Transaction]:
    """Generate a sequence of normal baseline transactions for a customer profile.

    :param customer: CustomerProfile providing baseline preferences.
    :param merchants: Pool of available merchants.
    :param count: Number of transactions to generate.
    :param rng: Seeded random number generator.
    :param base_time: Reference starting time (defaults to 2026-09-01T00:00:00 UTC).
    :param device_pool: Optional set of device IDs to rotate baseline transactions
        across (e.g. a customer's phone and laptop), so "known device" naturally
        covers more than one physical device. Defaults to None, which preserves
        the original single-device behavior bit-for-bit (every baseline
        transaction defaults to customer.primary_device_id inside
        generate_single_transaction, with no extra rng draw) -- every existing
        committed seed scenario's generation is completely unaffected by this
        parameter's addition.
    :return: List of valid Transaction models representing normal baseline behavior.
    """
    start_time = base_time or datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
    transactions: list[Transaction] = []

    current_time = start_time
    for i in range(count):
        # Normal customer transacts during daytime hours (09:00 - 21:00) with small random delta
        interval_hours = rng.randint(6, 36)
        current_time += timedelta(hours=interval_hours, minutes=rng.randint(0, 59))

        # Normal amount sampled around customer mean
        noise = Decimal(str(round(rng.gauss(0, float(customer.typical_amount_std)), 2)))
        amount = max(Decimal("5.00"), customer.typical_amount_mean + noise)

        merchant = rng.choice(merchants)
        channel = Channel.WEB if rng.random() > 0.3 else Channel.MOBILE
        device_id = rng.choice(device_pool) if device_pool else None

        tx = generate_single_transaction(
            transaction_id=f"tx_norm_{customer.customer_id}_{i:04d}",
            customer=customer,
            merchant=merchant,
            amount=amount,
            timestamp=current_time,
            channel=channel,
            device_id=device_id,
        )
        transactions.append(tx)

    return transactions
