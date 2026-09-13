"""Evidence fact contract for Sentinel V1."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict


class FactQuality(str, Enum):
    """Quality level of an evidence fact."""

    VERIFIED = "VERIFIED"
    DERIVED = "DERIVED"
    PARTIAL = "PARTIAL"


# Alias for domain consistency
Quality = FactQuality


class Fact(BaseModel):
    """Atomic unit of evidence gathered during investigation."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str
    type: str
    subject_id: str
    value: dict[str, object]
    source_tool: str
    source_record_id: str | None = None
    observed_at: datetime
    retrieved_at: datetime
    quality: FactQuality
