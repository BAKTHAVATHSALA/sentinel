"""Demo analyst workforce generation for Sentinel V1 (build.md Section 18-20).

Pure, dependency-free generation logic -- names, emails, passwords, role
assignment -- kept separate from `scripts/create_demo_analyst_workforce.py`
(which wires this to the real Firebase Admin SDK and Firestore) so it can be
unit-tested without touching any external service. Does not create Firebase
accounts or write to Firestore itself.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass

from shared.auth.models import AnalystRole

# Real, diverse, professional names -- never placeholder patterns like
# "Analyst 1" (build.md Section 18 explicitly prohibits that). Distinct from
# the three pre-existing demo accounts (Priya Nair / Marcus Webb / Elena Cho,
# scripts/seed_analyst_directory.py), which this script does not touch.
ANALYST_NAMES = [
    "Sofia Martinez",
    "Daniel Osei",
    "Wei Zhang",
    "Aisha Rahman",
    "Lucas Ferreira",
    "Naledi Dlamini",
    "Ethan Whitfield",
    "Meera Iyer",
    "Tomas Alvarez",
    "Yuki Tanaka",
    "Grace Okafor",
    "Omar Haddad",
    "Isabelle Laurent",
    "Ravi Chandran",
    "Chloe Bennett",
]

SENIOR_ANALYST_NAMES = [
    "Nadia Petrova",
    "Samuel Kim",
    "Fatima Al-Sayed",
    "Benjamin Cole",
    "Anjali Deshmukh",
    "Julian Novak",
    "Amara Nwosu",
]

EMAIL_DOMAIN = "sentinel.demo"


@dataclass(frozen=True)
class WorkforceMember:
    """One generated demo analyst, not yet created anywhere."""

    display_name: str
    email: str
    password: str
    role: AnalystRole


def _slugify_email_local_part(display_name: str) -> str:
    ascii_name = display_name.encode("ascii", "ignore").decode("ascii")
    return ascii_name.lower().replace(" ", ".").replace("-", "")


def generate_workforce(
    analyst_names: list[str] | None = None,
    senior_names: list[str] | None = None,
    password_factory: Callable[[], str] = lambda: secrets.token_urlsafe(12),
) -> list[WorkforceMember]:
    """Build the full demo workforce roster (names/emails/passwords), not yet
    persisted anywhere.

    :param analyst_names: Display names for ANALYST role; defaults to the 15 named above.
    :param senior_names: Display names for SENIOR_ANALYST role; defaults to the 7 named above.
    :param password_factory: Generates one strong password per call; injected for deterministic tests.
    :return: One WorkforceMember per name, emails guaranteed unique.
    :raises ValueError: if the resulting email addresses would collide (duplicate names).
    """
    names_with_roles = [(name, AnalystRole.ANALYST) for name in (analyst_names or ANALYST_NAMES)] + [
        (name, AnalystRole.SENIOR_ANALYST) for name in (senior_names or SENIOR_ANALYST_NAMES)
    ]

    members: list[WorkforceMember] = []
    seen_emails: set[str] = set()
    seen_passwords: set[str] = set()

    for display_name, role in names_with_roles:
        email = f"{_slugify_email_local_part(display_name)}@{EMAIL_DOMAIN}"
        if email in seen_emails:
            raise ValueError(f"Duplicate generated email '{email}' -- two names slugify to the same address")
        seen_emails.add(email)

        password = password_factory()
        while password in seen_passwords:  # pragma: no cover -- astronomically unlikely with token_urlsafe(12)
            password = password_factory()
        seen_passwords.add(password)

        members.append(WorkforceMember(display_name=display_name, email=email, password=password, role=role))

    return members
