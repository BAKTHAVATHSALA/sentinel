"""Decision Robustness Scorer contract for Sentinel V1 (Contracts v1.2 S18,
Build Checklist Phase 3.3).

RobustnessResult.classification is investigative and UI signal only -- it is
never an input to any Policy rule (S20). Policy evaluates only risk_score,
evidence.completeness, and findings.risk_assessment (S18.3).
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict


class RobustnessClassification(str, Enum):
    """Whether a case's risk assessment depends on a single removable factor."""

    ROBUST = "ROBUST"
    FRAGILE = "FRAGILE"


class RobustnessMethod(str, Enum):
    """Which of the two frozen scoring methods (S18.1/S18.2) produced a result."""

    FAST_PATH = "FAST_PATH"
    LIVE_COUNTERFACTUAL = "LIVE_COUNTERFACTUAL"


class RobustnessResult(BaseModel):
    """Output of the Decision Robustness Scorer for one case."""

    model_config = ConfigDict(extra="forbid")

    robustness_id: str
    case_id: str
    classification: RobustnessClassification
    fragile_factor_id: str | None = None
    method: RobustnessMethod
    evaluated_at: datetime
