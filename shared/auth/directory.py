"""Firestore-backed analyst directory for Sentinel V1 (V1 Authoritative Ruling
Part 2/5: a Sentinel-controlled directory keyed by Firebase UID, operationally
seeded -- no management UI, no ADMIN role).

Collection: {analysts}/{uid} -- one AnalystRecord per document, document ID
is the Firebase UID.
"""

from __future__ import annotations

from google.cloud import firestore

from shared.auth.models import AnalystRecord, AnalystRole

ANALYSTS_COLLECTION = "analysts"


class AnalystDirectory:
    """Firestore-backed lookup of analyst directory records."""

    def __init__(self, client: firestore.Client) -> None:
        """Initialize with an injected Firestore client so tests can substitute a fake.

        :param client: A google.cloud.firestore.Client (or a fake implementing the
            same collection() surface).
        """
        self._client = client

    def get(self, uid: str) -> AnalystRecord | None:
        """Look up one analyst directory record by Firebase UID.

        :param uid: Firebase UID to look up.
        :return: The AnalystRecord, or None if uid is not in the directory.
        """
        snapshot = self._client.collection(ANALYSTS_COLLECTION).document(uid).get()
        if not snapshot.exists:
            return None
        return AnalystRecord.model_validate({**(snapshot.to_dict() or {}), "uid": uid})

    def list_active_analysts(self) -> list[AnalystRecord]:
        """List every active ANALYST-role record, for round-robin assignment
        (V1 Authoritative Ruling Part 5: SENIOR_ANALYST users are excluded from
        normal assignment)."""
        return self._list_active_by_role(AnalystRole.ANALYST)

    def list_active_seniors(self) -> list[AnalystRecord]:
        """List every active SENIOR_ANALYST-role record, for the UI's escalation
        target dropdown (V1 Authoritative Ruling Part 4: name/email shown, raw UID
        never shown)."""
        return self._list_active_by_role(AnalystRole.SENIOR_ANALYST)

    def _list_active_by_role(self, role: AnalystRole) -> list[AnalystRecord]:
        query = self._client.collection(ANALYSTS_COLLECTION).where(
            filter=firestore.FieldFilter("role", "==", role.value)
        ).where(filter=firestore.FieldFilter("active", "==", True))
        return [AnalystRecord.model_validate({**(doc.to_dict() or {}), "uid": doc.id}) for doc in query.stream()]

    def upsert(self, record: AnalystRecord) -> None:
        """Create or replace one directory record (used by the operational seed
        script, never by application request handling)."""
        self._client.collection(ANALYSTS_COLLECTION).document(record.uid).set(
            record.model_dump(mode="json", exclude={"uid"})
        )
