"""Firebase Admin SDK token verification for Sentinel V1.

Authentication uses Firebase email/password sign-in (V1 Authoritative
Ruling Part 1); this module is the server side of that -- it verifies the
Firebase ID token a client sends and returns the token's claims (uid,
email). It never issues tokens and never trusts a client-supplied identity.

Application Default Credentials only -- no API key, no service account
JSON file (Contracts V1-Scoped S10/S23: no secrets committed to the repo).
The Cloud Run/local ADC identity already used for Vertex AI and Firestore
(shared.persistence.firestore_client) is reused here; Firebase Admin SDK
initializes once per process.
"""

from __future__ import annotations

import firebase_admin
from firebase_admin import auth as firebase_auth

from shared.config import get_gcp_project_id

_app: firebase_admin.App | None = None


def _get_app() -> firebase_admin.App:
    global _app
    if _app is None:
        _app = firebase_admin.initialize_app(options={"projectId": get_gcp_project_id()})
    return _app


class InvalidIdTokenError(Exception):
    """Raised when a Firebase ID token is missing, malformed, expired, or otherwise
    fails verification."""


def verify_id_token(id_token: str) -> dict[str, object]:
    """Verify a Firebase ID token and return its decoded claims.

    :param id_token: The raw ID token from an `Authorization: Bearer <token>` header.
    :return: Decoded token claims, including "uid" and "email".
    :raises InvalidIdTokenError: if the token fails verification for any reason.
    """
    try:
        return firebase_auth.verify_id_token(id_token, app=_get_app())
    except Exception as exc:  # noqa: BLE001 -- any verification failure must reject, not crash
        raise InvalidIdTokenError(str(exc)) from exc
