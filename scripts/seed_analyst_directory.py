"""Operational seed script for Sentinel V1's analyst directory (V1
Authoritative Ruling Part 2/5: "Analyst records can be seeded operationally
... No analyst-management UI is required").

Writes AnalystRecord documents to Firestore's `analysts` collection, keyed by
the Firebase UID of three real Firebase Auth accounts created for this demo
(email/password sign-in, provisioned via the Identity Toolkit REST API --
see README's Authentication section for how to reproduce this). Re-running
this script is safe: `upsert` replaces each record with the same values.

Run: python -m scripts.seed_analyst_directory
"""

from __future__ import annotations

from shared.auth.directory import AnalystDirectory
from shared.auth.models import AnalystRecord, AnalystRole
from shared.persistence.firestore_client import build_firestore_client

SEED_ANALYSTS = [
    AnalystRecord(
        uid="Kf7TBulMUnX9xOQYs6hNK9IBmTO2",
        email="analyst1@sentinel.demo",
        display_name="Priya Nair",
        role=AnalystRole.ANALYST,
        active=True,
    ),
    AnalystRecord(
        uid="EhgFAdXOTCPCV51bJ1j5ZavGGRc2",
        email="analyst2@sentinel.demo",
        display_name="Marcus Webb",
        role=AnalystRole.ANALYST,
        active=True,
    ),
    AnalystRecord(
        uid="kyDqtXKjN3S9DChS3Qy7qEGE5Lz2",
        email="senior1@sentinel.demo",
        display_name="Elena Cho",
        role=AnalystRole.SENIOR_ANALYST,
        active=True,
    ),
]


def seed_analyst_directory() -> list[AnalystRecord]:
    """Write every SEED_ANALYSTS record to Firestore and return what was written."""
    directory = AnalystDirectory(build_firestore_client())
    for record in SEED_ANALYSTS:
        directory.upsert(record)
    return SEED_ANALYSTS


if __name__ == "__main__":
    written = seed_analyst_directory()
    for record in written:
        print(f"seeded analysts/{record.uid}: {record.display_name} <{record.email}> role={record.role.value}")
