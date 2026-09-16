"""Analyst identity and role contracts for Sentinel V1's authentication layer.

Not part of the frozen `shared/contracts/*` package: those contracts model
the case/policy/reasoning domain, while these model who is calling the API.
Exactly two roles exist (V1 Authoritative Ruling Part 2/3): no ADMIN role.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class AnalystRole(str, Enum):
    """The exactly-two roles Sentinel V1 recognizes. Server-resolved only,
    never trusted from the client."""

    ANALYST = "ANALYST"
    SENIOR_ANALYST = "SENIOR_ANALYST"


class AnalystRecord(BaseModel):
    """A directory entry keyed by Firebase UID (V1 Authoritative Ruling Part 5:
    operationally seeded, no management UI)."""

    model_config = ConfigDict(extra="forbid")

    uid: str
    email: str
    display_name: str
    role: AnalystRole
    active: bool


class AuthenticatedAnalyst(BaseModel):
    """The resolved caller identity attached to a request after the Firebase ID
    token is verified and the UID is found active in the analyst directory."""

    model_config = ConfigDict(extra="forbid")

    uid: str
    email: str
    display_name: str
    role: AnalystRole
