"""Deterministic round-robin case assignment for Sentinel V1 (V1 Authoritative
Ruling Part 4/5, Addendum 1 Point 1/2):

- fires only at the moment a case first transitions into HUMAN_REVIEW
- pool is the active ANALYST directory only (SENIOR_ANALYST excluded)
- escalation later reassigns assigned_analyst_id directly and must never
  re-trigger this
- zero active analysts leaves the case genuinely unassigned (no
  auto-escalation, no fallback actor)

Collection: {system_state}/round_robin_pointer -- {"last_assigned_uid": ...}.
A Firestore transaction makes "read the pointer, pick the next analyst,
advance the pointer" atomic so two cases entering HUMAN_REVIEW concurrently
don't both land on the same analyst.
"""

from __future__ import annotations

from google.cloud import firestore

SYSTEM_STATE_COLLECTION = "system_state"
ROUND_ROBIN_POINTER_DOCUMENT = "round_robin_pointer"


class AssignmentStore:
    """Firestore-backed round-robin pointer for HUMAN_REVIEW case assignment."""

    def __init__(self, client: firestore.Client) -> None:
        """Initialize with an injected Firestore client so tests can substitute a fake.

        :param client: A google.cloud.firestore.Client (or a fake implementing the
            same collection()/transaction() surface).
        """
        self._client = client

    def assign_next_analyst(self, active_uids: list[str]) -> str | None:
        """Pick and record the next analyst in round-robin order.

        :param active_uids: Firebase UIDs of every currently active ANALYST
            (AnalystDirectory.list_active_analysts(), mapped to uid).
        :return: The assigned UID, or None if active_uids is empty (V1
            Authoritative Ruling Part 5: zero-analyst leaves the case unassigned,
            no auto-escalation).
        """
        if not active_uids:
            return None
        sorted_uids = sorted(set(active_uids))
        pointer_ref = self._client.collection(SYSTEM_STATE_COLLECTION).document(ROUND_ROBIN_POINTER_DOCUMENT)
        transaction = self._client.transaction()
        return _assign_next_txn(transaction, pointer_ref, sorted_uids)


@firestore.transactional
def _assign_next_txn(
    transaction: firestore.Transaction,
    pointer_ref: firestore.DocumentReference,
    sorted_uids: list[str],
) -> str:
    snapshot = pointer_ref.get(transaction=transaction)
    last_assigned = (snapshot.to_dict() or {}).get("last_assigned_uid") if snapshot.exists else None

    if last_assigned in sorted_uids:
        next_index = (sorted_uids.index(last_assigned) + 1) % len(sorted_uids)
    else:
        # Either the first-ever assignment, or the previously-assigned uid is
        # no longer in the active pool -- start from the front deterministically
        # rather than guessing where it "would have been".
        next_index = 0

    next_uid = sorted_uids[next_index]
    transaction.set(pointer_ref, {"last_assigned_uid": next_uid})
    return next_uid
