"""Creates Sentinel V1's demo analyst workforce: 15 ANALYST + 7 SENIOR_ANALYST
real Firebase Auth accounts, plus their Firestore `analysts/{uid}` directory
records (build.md Sections 18-20).

This is an EXTERNAL, PERSISTENT, COST-BEARING action (creates real Firebase
Authentication users in whatever GCP project ADC currently points at) --
per build.md Section 39, it must not run without explicit operator
confirmation, which is why `main()` requires the literal `--yes` flag. Import
and unit-test `shared.auth.workforce.generate_workforce` instead of running
this script to verify the generation logic.

Idempotent: re-running looks up any account that already exists by email
and resets its password to the freshly generated one (so the credentials
output file is always accurate to what was actually written), rather than
failing or creating a duplicate.

Run: python -m scripts.create_demo_analyst_workforce --yes
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Protocol

from shared.auth.directory import AnalystDirectory
from shared.auth.models import AnalystRecord
from shared.auth.workforce import WorkforceMember, generate_workforce
from shared.persistence.firestore_client import build_firestore_client

CREDENTIALS_OUTPUT_PATH = Path("local/demo_analyst_credentials.json")


class AuthUserManager(Protocol):
    """The slice of firebase_admin.auth this script needs -- injectable so
    tests never touch a real Firebase project."""

    def create_user(self, email: str, password: str, display_name: str) -> str:
        """Create a new user; returns the new Firebase UID."""
        ...

    def get_uid_by_email(self, email: str) -> str | None:
        """Look up an existing user's UID by email, or None if not found."""
        ...

    def set_password(self, uid: str, password: str, display_name: str) -> None:
        """Reset an existing user's password/display name to keep the
        credentials output file accurate on a re-run."""
        ...


class FirebaseAdminAuthUserManager:
    """Real implementation, wired to firebase_admin.auth (Application
    Default Credentials only -- no service account JSON, matching every
    other Firebase Admin usage in this repo). Reuses
    shared.auth.firebase_admin_client's app singleton so this script targets
    the exact same project (GCP_PROJECT_ID / DEFAULT_GCP_PROJECT_ID =
    "sentinel-ai-builder-cup") as the running API server, rather than
    initializing a second, independently-configured Firebase app."""

    def __init__(self) -> None:
        from shared.auth.firebase_admin_client import _get_app

        self._app = _get_app()

    def create_user(self, email: str, password: str, display_name: str) -> str:
        from firebase_admin import auth as firebase_auth

        user = firebase_auth.create_user(email=email, password=password, display_name=display_name, app=self._app)
        return user.uid

    def get_uid_by_email(self, email: str) -> str | None:
        from firebase_admin import auth as firebase_auth

        try:
            return firebase_auth.get_user_by_email(email, app=self._app).uid
        except firebase_auth.UserNotFoundError:
            return None

    def set_password(self, uid: str, password: str, display_name: str) -> None:
        from firebase_admin import auth as firebase_auth

        firebase_auth.update_user(uid, password=password, display_name=display_name, app=self._app)


def create_workforce(
    members: list[WorkforceMember],
    auth_manager: AuthUserManager,
    directory: AnalystDirectory,
) -> list[dict[str, str]]:
    """Create/update every member's Firebase Auth account and Firestore
    directory record. Returns the credentials rows to write locally.

    :param members: The generated roster (shared.auth.workforce.generate_workforce).
    :param auth_manager: Injected Firebase Auth user manager (real or fake).
    :param directory: Injected AnalystDirectory (real or fake).
    :return: One dict per member: display_name, email, password, role, uid.
    """
    credentials: list[dict[str, str]] = []
    for member in members:
        existing_uid = auth_manager.get_uid_by_email(member.email)
        if existing_uid is not None:
            auth_manager.set_password(existing_uid, member.password, member.display_name)
            uid = existing_uid
        else:
            uid = auth_manager.create_user(member.email, member.password, member.display_name)

        directory.upsert(
            AnalystRecord(uid=uid, email=member.email, display_name=member.display_name, role=member.role, active=True)
        )

        credentials.append(
            {"uid": uid, "display_name": member.display_name, "email": member.email, "password": member.password, "role": member.role.value}
        )
    return credentials


def write_credentials_file(rows: list[dict[str, str]], path: Path = CREDENTIALS_OUTPUT_PATH) -> None:
    """Writes credentials locally. The path MUST already be covered by
    .gitignore -- this function does not check that itself (verified once,
    operationally, by the .gitignore entry added alongside this script)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main() -> None:
    if "--yes" not in sys.argv:
        print(
            "This creates real, persistent Firebase Authentication accounts in whatever GCP "
            "project Application Default Credentials currently points at, plus matching Firestore "
            "analyst directory records. Re-run with --yes to proceed.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    members = generate_workforce()
    directory = AnalystDirectory(build_firestore_client())
    rows = create_workforce(members, FirebaseAdminAuthUserManager(), directory)
    write_credentials_file(rows)

    analyst_count = sum(1 for r in rows if r["role"] == "ANALYST")
    senior_count = sum(1 for r in rows if r["role"] == "SENIOR_ANALYST")
    print(f"Created/updated {len(rows)} demo analyst accounts ({analyst_count} ANALYST, {senior_count} SENIOR_ANALYST).")
    print(f"Credentials written to {CREDENTIALS_OUTPUT_PATH} (gitignored -- do not commit).")


if __name__ == "__main__":
    main()
