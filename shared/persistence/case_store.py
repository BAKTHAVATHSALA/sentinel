"""Firestore case store for Sentinel V1 (Contracts V1-Scoped S20/S21/S25,
Build Checklist Phase 4.2).

Collections:
  {transactions}/{transaction_id}  -- idempotency marker: {"case_id": ...}.
      A transaction_id maps to at most one case, ever (Contracts V1-Scoped
      S4 "A transaction may have at most one active investigation case").
      create_case_if_new() creates this marker and the case document
      together inside one Firestore transaction, so two concurrent
      POST /transactions requests for the same transaction_id cannot create
      two cases (Safety Invariants 8/9) -- the loser reads back the
      winner's case_id instead.
  {cases}/{case_id}                -- the case document (case_document.py).
  {cases}/{case_id}/{audit}/{audit_event_id} -- one entry per state
      transition (Contracts V1-Scoped S21).

Collection names are configurable (shared.config) but default to
"transactions", "cases", "audit_events".
"""

from __future__ import annotations

from google.cloud import firestore

from shared.config import (
    get_firestore_audit_collection,
    get_firestore_cases_collection,
    get_firestore_transactions_collection,
)
from shared.contracts.events import AuditEvent


class CaseStore:
    """Firestore-backed case store: creation idempotency, updates, and the audit trail."""

    def __init__(self, client: firestore.Client) -> None:
        """Initialize with an injected Firestore client so tests can substitute a fake.

        :param client: A google.cloud.firestore.Client (or a fake implementing the
            same collection()/transaction() surface).
        """
        self._client = client
        self._transactions_collection = get_firestore_transactions_collection()
        self._cases_collection = get_firestore_cases_collection()
        self._audit_collection = get_firestore_audit_collection()

    def create_case_if_new(self, transaction_id: str, case_id: str, document: dict[str, object]) -> tuple[bool, str]:
        """Atomically create a case for transaction_id, unless one already exists.

        :param transaction_id: Transaction this case investigates.
        :param case_id: Case identifier to create if none exists yet.
        :param document: The case document (case_document.build_case_document()) to write.
        :return: (created, resolved_case_id) -- created is False and resolved_case_id is the
            existing case_id if a case for this transaction_id already existed (Safety
            Invariants 8/9: duplicate delivery must not create a second case).
        """
        tx_marker_ref = self._client.collection(self._transactions_collection).document(transaction_id)
        case_ref = self._client.collection(self._cases_collection).document(case_id)
        transaction = self._client.transaction()
        return _create_case_if_new_txn(transaction, tx_marker_ref, case_ref, case_id, document)

    def get_case_id_for_transaction(self, transaction_id: str) -> str | None:
        """Look up the existing case_id for a transaction_id, if any.

        :param transaction_id: Transaction to look up.
        :return: The existing case_id, or None if no case exists yet.
        """
        snapshot = self._client.collection(self._transactions_collection).document(transaction_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        return data.get("case_id")

    def update_case(self, case_id: str, updates: dict[str, object]) -> None:
        """Merge-update fields on an existing case document.

        :param case_id: Case to update.
        :param updates: Fields to merge into the existing document.
        """
        self._client.collection(self._cases_collection).document(case_id).set(updates, merge=True)

    def get_case(self, case_id: str) -> dict[str, object] | None:
        """Fetch a case document by case_id.

        :param case_id: Case to fetch.
        :return: The case document dict, or None if it does not exist.
        """
        snapshot = self._client.collection(self._cases_collection).document(case_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def append_audit_event(self, case_id: str, audit_event: AuditEvent) -> None:
        """Append one audit event to a case's audit_events subcollection.

        :param case_id: Case this event belongs to.
        :param audit_event: The AuditEvent to record (Contracts V1-Scoped S21).
        """
        ref = (
            self._client.collection(self._cases_collection)
            .document(case_id)
            .collection(self._audit_collection)
            .document(audit_event.audit_event_id)
        )
        ref.set(audit_event.model_dump(mode="json"))


@firestore.transactional
def _create_case_if_new_txn(
    transaction: firestore.Transaction,
    tx_marker_ref: firestore.DocumentReference,
    case_ref: firestore.DocumentReference,
    case_id: str,
    document: dict[str, object],
) -> tuple[bool, str]:
    snapshot = tx_marker_ref.get(transaction=transaction)
    if snapshot.exists:
        existing = snapshot.to_dict() or {}
        return False, existing.get("case_id", case_id)

    transaction.set(tx_marker_ref, {"case_id": case_id})
    transaction.set(case_ref, document)
    return True, case_id
