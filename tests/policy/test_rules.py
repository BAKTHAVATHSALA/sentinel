"""Unit tests for the Policy rule set as versioned data (Contracts V1-Scoped
S15/S16, Build Checklist Phase 4.1) -- sanity checks on shape, ordering, and
the non-negotiable BLOCK_HOLD authority boundary."""

from __future__ import annotations

import ast
from pathlib import Path

from shared.contracts.policy import PolicyOutcome
from shared.policy.rules import POLICY_RULES


def test_exactly_five_rules_matching_the_frozen_contract() -> None:
    """Contracts V1-Scoped S16 defines P-001..P-004 plus the mandatory Otherwise rule."""
    assert [r.rule_id for r in POLICY_RULES] == ["P-001", "P-002", "P-003", "P-004", "P-005"]


def test_rules_are_sorted_ascending_by_priority() -> None:
    priorities = [r.priority for r in POLICY_RULES]
    assert priorities == sorted(priorities)
    assert len(set(priorities)) == len(priorities)


def test_all_rules_enabled_by_default() -> None:
    assert all(r.enabled for r in POLICY_RULES)


def test_otherwise_rule_is_last_and_has_highest_priority_number() -> None:
    assert POLICY_RULES[-1].rule_id == "P-005"
    assert POLICY_RULES[-1].priority == max(r.priority for r in POLICY_RULES)


def test_policy_outcome_enum_has_exactly_two_members() -> None:
    """Type-level guarantee: PolicyOutcome cannot represent BLOCK_HOLD or AUTO_DECLINE."""
    assert {member.value for member in PolicyOutcome} == {"AUTO_RESOLVE", "ESCALATE"}


def test_only_p004_produces_auto_resolve() -> None:
    auto_resolve_rules = [r.rule_id for r in POLICY_RULES if r.outcome == PolicyOutcome.AUTO_RESOLVE]
    assert auto_resolve_rules == ["P-004"]


def test_no_policy_source_file_uses_block_hold_as_a_code_value() -> None:
    """Build Checklist Phase 4.1: confirm no path can produce BLOCK_HOLD from this component.

    Checks the AST for a standalone string constant exactly equal to
    "BLOCK_HOLD" (i.e. used as a value -- an outcome, a dict key, a
    comparison), not a plain substring match, so docstrings/comments that
    *discuss* the invariant (e.g. "never BLOCK_HOLD") don't false-positive.
    """
    policy_dir = Path(__file__).resolve().parents[2] / "shared" / "policy"
    offenders = []
    for path in policy_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "BLOCK_HOLD":
                offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], f"'BLOCK_HOLD' used as a code value outside the human-decision contract: {offenders}"
