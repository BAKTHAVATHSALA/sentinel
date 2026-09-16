"""FastAPI dependencies enforcing Sentinel V1's authentication/RBAC boundary
(V1 Authoritative Ruling Part 1/2, Addendum 1 Point 5).

Every protected /cases request must verify the Firebase ID token server-side
and resolve the caller's role from the Sentinel-controlled analyst directory
-- never from anything the client supplies. An authenticated Firebase user
who has no active directory record is rejected (Part 2: "Authenticated but
unregistered users must be rejected").
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from shared.auth.directory import AnalystDirectory
from shared.auth.firebase_admin_client import InvalidIdTokenError, verify_id_token
from shared.auth.models import AuthenticatedAnalyst
from shared.persistence.firestore_client import build_firestore_client


def get_analyst_directory() -> AnalystDirectory:
    """FastAPI dependency: the real Firestore-backed AnalystDirectory.

    Overridden in tests via app.dependency_overrides to inject a fake directory.
    """
    return AnalystDirectory(build_firestore_client())


def get_current_analyst(
    authorization: str | None = Header(default=None),
    directory: AnalystDirectory = Depends(get_analyst_directory),
) -> AuthenticatedAnalyst:
    """Resolve and authorize the caller from their Firebase ID token.

    :param authorization: The raw `Authorization` header, expected as `Bearer <id_token>`.
    :param directory: Analyst directory to resolve the verified UID's role against.
    :return: The authenticated, authorized caller.
    :raises HTTPException: 401 if the token is missing/invalid, 403 if the verified
        UID has no active directory record.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    id_token = authorization[len("Bearer "):].strip()
    try:
        claims = verify_id_token(id_token)
    except InvalidIdTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid ID token: {exc}") from exc

    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="ID token has no subject")

    record = directory.get(str(uid))
    if record is None or not record.active:
        raise HTTPException(status_code=403, detail="This account is not a registered active analyst")

    return AuthenticatedAnalyst(uid=record.uid, email=record.email, display_name=record.display_name, role=record.role)
