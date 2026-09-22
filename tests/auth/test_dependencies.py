"""Unit tests for shared/auth/dependencies.py's get_current_analyst -- the
FastAPI dependency every protected /cases endpoint depends on. Firebase token
verification itself is monkeypatched (deterministic, no network dependency);
the real Firebase Admin SDK call is covered separately by
tests/auth/test_dependencies_live.py."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from shared.auth import dependencies
from shared.auth.dependencies import get_analyst_directory, get_current_analyst
from shared.auth.firebase_admin_client import InvalidIdTokenError
from shared.auth.models import AnalystRecord, AnalystRole


class FakeAnalystDirectory:
    def __init__(self, records: dict[str, AnalystRecord] | None = None) -> None:
        self._records = records or {}

    def get(self, uid: str) -> AnalystRecord | None:
        return self._records.get(uid)


def _record(uid: str, role: AnalystRole = AnalystRole.ANALYST, active: bool = True) -> AnalystRecord:
    return AnalystRecord(uid=uid, email=f"{uid}@sentinel.demo", display_name=uid, role=role, active=active)


def test_missing_authorization_header_is_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_analyst(authorization=None, directory=FakeAnalystDirectory())
    assert exc_info.value.status_code == 401


def test_malformed_authorization_header_is_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_analyst(authorization="Basic xyz", directory=FakeAnalystDirectory())
    assert exc_info.value.status_code == 401


def test_invalid_token_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_verify(_token: str) -> dict[str, object]:
        raise InvalidIdTokenError("token expired")

    monkeypatch.setattr(dependencies, "verify_id_token", fake_verify)

    with pytest.raises(HTTPException) as exc_info:
        get_current_analyst(authorization="Bearer bad_token", directory=FakeAnalystDirectory())
    assert exc_info.value.status_code == 401


def test_valid_token_but_unregistered_uid_is_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "verify_id_token", lambda _t: {"uid": "uid_unregistered"})

    with pytest.raises(HTTPException) as exc_info:
        get_current_analyst(authorization="Bearer good_token", directory=FakeAnalystDirectory())
    assert exc_info.value.status_code == 403


def test_valid_token_but_inactive_directory_record_is_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "verify_id_token", lambda _t: {"uid": "uid_inactive"})
    directory = FakeAnalystDirectory({"uid_inactive": _record("uid_inactive", active=False)})

    with pytest.raises(HTTPException) as exc_info:
        get_current_analyst(authorization="Bearer good_token", directory=directory)
    assert exc_info.value.status_code == 403


def test_valid_authenticated_analyst_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "verify_id_token", lambda _t: {"uid": "uid_analyst"})
    directory = FakeAnalystDirectory({"uid_analyst": _record("uid_analyst", role=AnalystRole.ANALYST)})

    caller = get_current_analyst(authorization="Bearer good_token", directory=directory)

    assert caller.uid == "uid_analyst"
    assert caller.role == AnalystRole.ANALYST


def test_valid_senior_analyst_resolves_with_senior_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "verify_id_token", lambda _t: {"uid": "uid_senior"})
    directory = FakeAnalystDirectory({"uid_senior": _record("uid_senior", role=AnalystRole.SENIOR_ANALYST)})

    caller = get_current_analyst(authorization="Bearer good_token", directory=directory)

    assert caller.role == AnalystRole.SENIOR_ANALYST


def test_get_analyst_directory_dependency_builds_a_real_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke test only: confirms the default dependency factory wires up an
    AnalystDirectory without raising, and that endpoints override it in tests
    rather than depending on this real construction path."""
    fake_firestore_client = object()
    monkeypatch.setattr(dependencies, "build_firestore_client", lambda: fake_firestore_client)

    directory = get_analyst_directory()
    assert directory.__class__.__name__ == "AnalystDirectory"
