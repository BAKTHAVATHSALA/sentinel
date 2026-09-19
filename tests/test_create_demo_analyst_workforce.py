"""Unit tests for scripts/create_demo_analyst_workforce.py's persistence
logic (build.md Section 18-20/36 SEEDING). No real Firebase project or
Firestore is ever touched -- AuthUserManager and AnalystDirectory are both
fakes. This script is never invoked end-to-end (main()) in tests; only
`create_workforce` and `write_credentials_file`, which is exactly what
build.md Section 39 requires (code + tests ready, execution gated on
explicit operator approval)."""

from __future__ import annotations

import json

from shared.auth.models import AnalystRecord, AnalystRole
from shared.auth.workforce import generate_workforce
from scripts.create_demo_analyst_workforce import create_workforce, write_credentials_file


class FakeAuthUserManager:
    """In-memory double: email -> uid, plus a record of every password set."""

    def __init__(self) -> None:
        self._uid_by_email: dict[str, str] = {}
        self._next_uid = 0
        self.created_emails: list[str] = []
        self.password_resets: list[str] = []

    def create_user(self, email: str, password: str, display_name: str) -> str:
        self._next_uid += 1
        uid = f"fake_uid_{self._next_uid}"
        self._uid_by_email[email] = uid
        self.created_emails.append(email)
        return uid

    def get_uid_by_email(self, email: str) -> str | None:
        return self._uid_by_email.get(email)

    def set_password(self, uid: str, password: str, display_name: str) -> None:
        self.password_resets.append(uid)


class FakeAnalystDirectory:
    def __init__(self) -> None:
        self.records: dict[str, AnalystRecord] = {}

    def upsert(self, record: AnalystRecord) -> None:
        self.records[record.uid] = record


def test_creates_22_accounts_with_correct_role_split() -> None:
    members = generate_workforce()
    auth_manager = FakeAuthUserManager()
    directory = FakeAnalystDirectory()

    rows = create_workforce(members, auth_manager, directory)

    assert len(rows) == 22
    assert len(auth_manager.created_emails) == 22
    assert len(directory.records) == 22
    analyst_count = sum(1 for r in directory.records.values() if r.role == AnalystRole.ANALYST)
    senior_count = sum(1 for r in directory.records.values() if r.role == AnalystRole.SENIOR_ANALYST)
    assert analyst_count == 15
    assert senior_count == 7


def test_every_directory_record_is_active() -> None:
    rows = create_workforce(generate_workforce(), FakeAuthUserManager(), FakeAnalystDirectory())
    directory = FakeAnalystDirectory()
    create_workforce(generate_workforce(), FakeAuthUserManager(), directory)
    assert all(record.active for record in directory.records.values())
    assert len(rows) == 22  # sanity: first call's rows unaffected by the second directory


def test_analyst_record_has_no_password_field() -> None:
    """AnalystRecord (extra="forbid") structurally cannot carry a password --
    Firestore never stores one (build.md Section 20)."""
    assert "password" not in AnalystRecord.model_fields


def test_rerun_is_idempotent_and_resets_password_instead_of_duplicating() -> None:
    members = generate_workforce()
    auth_manager = FakeAuthUserManager()
    directory = FakeAnalystDirectory()

    first_run = create_workforce(members, auth_manager, directory)
    second_run = create_workforce(members, auth_manager, directory)

    assert len(auth_manager.created_emails) == 22  # never created twice
    assert len(auth_manager.password_resets) == 22  # second run reset every password instead
    assert {r["uid"] for r in first_run} == {r["uid"] for r in second_run}
    assert len(directory.records) == 22  # no duplicate directory entries


def test_credentials_file_contains_every_generated_password(tmp_path) -> None:
    members = generate_workforce()
    rows = create_workforce(members, FakeAuthUserManager(), FakeAnalystDirectory())
    output_path = tmp_path / "demo_analyst_credentials.json"

    write_credentials_file(rows, path=output_path)

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(written) == 22
    assert {row["password"] for row in written} == {m.password for m in members}
    assert all("uid" in row and "email" in row and "display_name" in row and "role" in row for row in written)


def test_gitignore_covers_the_credentials_output_directory() -> None:
    gitignore = open(".gitignore", encoding="utf-8").read()
    assert "/local/" in gitignore
