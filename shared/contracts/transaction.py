"""Transaction contract and related domain types for Sentinel V1."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict


class PaymentRail(str, Enum):
    """Supported payment rail for transaction processing."""

    CARD_CNP = "CARD_CNP"


class Direction(str, Enum):
    """Direction of funds transfer for the transaction."""

    OUTGOING = "OUTGOING"


class AuthorizationStage(str, Enum):
    """Lifecycle authorization stage of the transaction."""

    PRE_AUTH = "PRE_AUTH"
    AUTH = "AUTH"
    SETTLED = "SETTLED"


class Channel(str, Enum):
    """Channel through which the transaction was initiated."""

    WEB = "WEB"
    MOBILE = "MOBILE"


class Geo(BaseModel):
    """Geographic coordinates and country associated with a transaction location."""

    lat: Decimal
    lon: Decimal
    country: str


class Transaction(BaseModel):
    """Core domain transaction entity for Sentinel V1 fraud investigation."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    customer_id: str
    account_id: str
    card_id: str
    merchant_id: str

    amount: Decimal
    currency: str
    timestamp: datetime

    payment_rail: PaymentRail
    direction: Direction
    authorization_stage: AuthorizationStage

    device_id: str
    ip_address: str
    geo: Geo

    channel: Channel
    merchant_category: str
    card_present: bool
