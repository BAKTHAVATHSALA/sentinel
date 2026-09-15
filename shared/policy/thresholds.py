"""Evaluation-tuned Policy thresholds for Sentinel V1 (Contracts V1-Scoped
S16 Rule P-003, S29 Evaluation Contract).

HIGH_VALUE_THRESHOLD is derived from the held-out evaluation split, not
guessed -- see scripts/derive_policy_thresholds.py and the saved artifact
eval/policy_thresholds.json for the full derivation and cost-of-error
rationale. Hardcoded here (mirroring shared/detection/model.py's
LOW_RISK_THRESHOLD/HIGH_RISK_THRESHOLD pattern) so Policy has no runtime
dependency on reading the eval JSON file.
"""

from __future__ import annotations

from decimal import Decimal

# ~95th percentile of legitimate transaction amounts in the held-out split
# (data/processed/held_out.csv) -- see eval/policy_thresholds.json.
HIGH_VALUE_THRESHOLD = Decimal("375.00")
