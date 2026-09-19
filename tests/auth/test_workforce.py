"""Unit tests for the demo analyst workforce generator (build.md Section 18-20).
No Firebase or Firestore involved -- pure generation logic only."""

from __future__ import annotations

import pytest

from shared.auth.models import AnalystRole
from shared.auth.workforce import ANALYST_NAMES, SENIOR_ANALYST_NAMES, generate_workforce


def test_generates_exactly_15_analyst_and_7_senior_analyst() -> None:
    members = generate_workforce()
    analysts = [m for m in members if m.role == AnalystRole.ANALYST]
    seniors = [m for m in members if m.role == AnalystRole.SENIOR_ANALYST]
    assert len(analysts) == 15
    assert len(seniors) == 7
    assert len(members) == 22


def test_no_placeholder_names() -> None:
    for name in ANALYST_NAMES + SENIOR_ANALYST_NAMES:
        assert "analyst" not in name.lower()
        assert "user" not in name.lower()
        assert not any(char.isdigit() for char in name)


def test_all_names_distinct() -> None:
    all_names = ANALYST_NAMES + SENIOR_ANALYST_NAMES
    assert len(set(all_names)) == len(all_names)


def test_all_emails_unique() -> None:
    members = generate_workforce()
    emails = [m.email for m in members]
    assert len(set(emails)) == len(emails) == 22


def test_all_emails_use_the_demo_domain() -> None:
    for member in generate_workforce():
        assert member.email.endswith("@sentinel.demo")


def test_all_passwords_unique() -> None:
    members = generate_workforce()
    passwords = [m.password for m in members]
    assert len(set(passwords)) == len(passwords) == 22


def test_passwords_are_reasonably_strong() -> None:
    for member in generate_workforce():
        assert len(member.password) >= 12


def test_duplicate_names_raise_instead_of_silently_colliding_emails() -> None:
    with pytest.raises(ValueError, match="Duplicate generated email"):
        generate_workforce(analyst_names=["Jordan Lee", "Jordan Lee"], senior_names=[])
