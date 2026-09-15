"""Sentinel V1 Policy rules as versioned data (Contracts V1-Scoped S15/S16,
Build Checklist Phase 4.1) -- not if/else logic scattered through the
codebase. shared.policy.evaluator is the single pure function that walks
this list, in priority order, against one case's inputs.

These are the frozen rules from Contracts V1-Scoped S16, exactly as
numbered there: P-001 through P-004, plus the mandatory Otherwise rule.
`outcome` is restricted to AUTO_RESOLVE | ESCALATE by the PolicyRule
contract itself -- no rule here can be authored to produce BLOCK_HOLD.
"""

from __future__ import annotations

from datetime import datetime, timezone

from shared.contracts.policy import PolicyOutcome, PolicyRule

RULE_SET_VERSION = "1.0.0"

# When this rule set went into effect -- Phase 4 build date.
RULES_EFFECTIVE_FROM = datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc)

P_001_INCOMPLETE_EVIDENCE = PolicyRule(
    rule_id="P-001",
    version=RULE_SET_VERSION,
    priority=10,
    condition="evidence.completeness = PARTIAL",
    outcome=PolicyOutcome.ESCALATE,
    effective_from=RULES_EFFECTIVE_FROM,
    enabled=True,
)

P_002_RISK_ASSESSMENT_TIGHTENING = PolicyRule(
    rule_id="P-002",
    version=RULE_SET_VERSION,
    priority=20,
    condition=(
        "risk_score >= MEDIUM AND findings.risk_assessment = HIGH AND evidence.completeness = COMPLETE"
    ),
    outcome=PolicyOutcome.ESCALATE,
    effective_from=RULES_EFFECTIVE_FROM,
    enabled=True,
)

P_003_HIGH_VALUE = PolicyRule(
    rule_id="P-003",
    version=RULE_SET_VERSION,
    priority=30,
    condition=(
        "risk_score >= HIGH AND amount >= HIGH_VALUE_THRESHOLD AND evidence.completeness = COMPLETE"
    ),
    outcome=PolicyOutcome.ESCALATE,
    effective_from=RULES_EFFECTIVE_FROM,
    enabled=True,
)

P_004_LOW_RISK_AUTO_RESOLVE = PolicyRule(
    rule_id="P-004",
    version=RULE_SET_VERSION,
    priority=40,
    condition=(
        "risk_score <= LOW AND evidence.completeness = COMPLETE "
        "AND (anomaly_tags ∩ HARD_RISK_TAGS) = ∅ AND findings.risk_assessment != HIGH"
    ),
    outcome=PolicyOutcome.AUTO_RESOLVE,
    effective_from=RULES_EFFECTIVE_FROM,
    enabled=True,
)

P_OTHERWISE = PolicyRule(
    rule_id="P-005",
    version=RULE_SET_VERSION,
    priority=999,
    condition="OTHERWISE",
    outcome=PolicyOutcome.ESCALATE,
    effective_from=RULES_EFFECTIVE_FROM,
    enabled=True,
)

# Ordered by priority ascending -- shared.policy.evaluator evaluates in this
# order and returns on the first enabled rule whose predicate matches.
# P_OTHERWISE's predicate is unconditionally true, so it always matches if
# nothing else did.
POLICY_RULES: tuple[PolicyRule, ...] = (
    P_001_INCOMPLETE_EVIDENCE,
    P_002_RISK_ASSESSMENT_TIGHTENING,
    P_003_HIGH_VALUE,
    P_004_LOW_RISK_AUTO_RESOLVE,
    P_OTHERWISE,
)
