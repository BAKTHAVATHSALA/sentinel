"""Live Firestore tests for shared/auth/directory.py, against the real
`sentinel-ai-builder-cup` project (Application Default Credentials) -- the
same real-infrastructure pattern as tests/persistence/test_case_store_live.py.
Writes/reads a disposable test UID, never touching the real seeded analysts
scripts/seed_analyst_directory.py writes."""

from __future__ import annotations

import uuid

import pytest

from shared.auth.directory import AnalystDirectory
from shared.auth.models import AnalystRecord, AnalystRole
from shared.persistence.firestore_client import build_firestore_client


@pytest.fixture()
def directory() -> AnalystDirectory:
    return AnalystDirectory(build_firestore_client())


def test_get_returns_none_for_unknown_uid(directory: AnalystDirectory) -> None:
    assert directory.get(f"uid_does_not_exist_{uuid.uuid4().hex}") is None


def test_upsert_then_get_round_trips(directory: AnalystDirectory) -> None:
    uid = f"test_analyst_{uuid.uuid4().hex[:10]}"
    record = AnalystRecord(
        uid=uid, email=f"{uid}@sentinel.demo", display_name="Test Analyst", role=AnalystRole.ANALYST, active=True
    )

    directory.upsert(record)
    fetched = directory.get(uid)

    assert fetched == record


def test_list_active_analysts_includes_the_real_seeded_analysts(directory: AnalystDirectory) -> None:
    """scripts/seed_analyst_directory.py has been run against this real project
    (README's Authentication section documents how) -- this proves the query
    that shared/pipeline/orchestrator.py's round-robin assignment depends on
    actually returns real, active ANALYST-role directory entries, not just
    what a fake returns."""
    active = directory.list_active_analysts()
    uids = {record.uid for record in active}

    assert "Kf7TBulMUnX9xOQYs6hNK9IBmTO2" in uids  # analyst1@sentinel.demo
    assert "EhgFAdXOTCPCV51bJ1j5ZavGGRc2" in uids  # analyst2@sentinel.demo
    assert all(record.role == AnalystRole.ANALYST for record in active)
    assert all(record.active for record in active)


def test_list_active_seniors_includes_the_real_seeded_senior(directory: AnalystDirectory) -> None:
    active = directory.list_active_seniors()
    uids = {record.uid for record in active}

    assert "kyDqtXKjN3S9DChS3Qy7qEGE5Lz2" in uids  # senior1@sentinel.demo
    assert all(record.role == AnalystRole.SENIOR_ANALYST for record in active)
