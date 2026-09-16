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
from google.cloud.firestore_v1.base_query import FieldFilter

from shared.config import (
    get_firestore_audit_collection,
    get_firestore_cases_collection,
    get_firestore_transactions_collection,
)
from shared.contracts.case import CaseState
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

    def list_cases_by_state(self, state: str) -> list[dict[str, object]]:
        """List every case document currently in the given state.

        A single-field equality filter on `state` is auto-indexed by Firestore
        (Contracts V1-Scoped S26: only build indexes actual query patterns need).

        :param state: CaseState value to filter on (e.g. "HUMAN_REVIEW" for the
            Build Checklist Phase 5.1 queue view).
        :return: Case documents in that state, each with its Firestore document id
            attached as "case_id" (defensive -- the field is already stored, but this
            guarantees it's present even for a document written before that field existed).
        """
        query = self._client.collection(self._cases_collection).where(filter=FieldFilter("state", "==", state))
        return [{**(doc.to_dict() or {}), "case_id": doc.id} for doc in query.stream()]

    def list_cases_by_state_and_assigned_analyst(self, state: str, assigned_analyst_id: str) -> list[dict[str, object]]:
        """List every case document in the given state, assigned to one analyst
        (Build Checklist Phase 5.1 queue view, V1 Authoritative Ruling Part 6:
        "GET /cases must be scoped to assigned_analyst_id == authenticated
        caller's Firebase UID -- there is NO global analyst queue in V1").

        :param state: CaseState value to filter on (HUMAN_REVIEW for the queue view).
        :param assigned_analyst_id: Firebase UID of the authenticated caller.
        :return: Case documents matching both filters.
        """
        query = (
            self._client.collection(self._cases_collection)
            .where(filter=FieldFilter("state", "==", state))
            .where(filter=FieldFilter("assigned_analyst_id", "==", assigned_analyst_id))
        )
        return [{**(doc.to_dict() or {}), "case_id": doc.id} for doc in query.stream()]

    def apply_human_decision(
        self,
        case_id: str,
        caller_uid: str,
        action: str,
        reason: str,
        target_analyst_id: str | None,
        updates: dict[str, object],
        audit_event: AuditEvent,
    ) -> tuple[str, dict[str, object]]:
        """Atomically verify eligibility and apply one human decision (V1
        Authoritative Ruling Part 8: "FIRST VALID HUMAN DECISION WINS").

        Re-checks state *and* current ownership (assigned_analyst_id) inside the
        Firestore transaction, not just before it -- a concurrent decision or a
        concurrent escalation can change either between the pre-check the caller
        (services/api/cases.py) already did and this write, and only the
        transaction's own read is trustworthy.

        :param case_id: Case to decide.
        :param caller_uid: Verified Firebase UID of the analyst making this request.
        :param action: "CLEAR" | "BLOCK_HOLD" | "ESCALATE_SENIOR".
        :param reason: The request's reason/explanation text.
        :param target_analyst_id: Selected senior's UID, for ESCALATE_SENIOR only.
        :param updates: Fields to merge into the case document if this request applies.
        :param audit_event: Audit event to write atomically with a successful apply.
        :return: (outcome, document) where outcome is "applied", "idempotent",
            "conflict", or "not_found". "conflict"/"not_found" documents are the
            current persisted state (possibly {}), never mutated by this call.
        """
        case_ref = self._client.collection(self._cases_collection).document(case_id)
        audit_ref = case_ref.collection(self._audit_collection).document(audit_event.audit_event_id)
        transaction = self._client.transaction()
        return _apply_human_decision_txn(
            transaction,
            case_ref,
            audit_ref,
            caller_uid,
            action,
            reason,
            target_analyst_id,
            updates,
            audit_event.model_dump(mode="json"),
        )

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


@firestore.transactional
def _apply_human_decision_txn(
    transaction: firestore.Transaction,
    case_ref: firestore.DocumentReference,
    audit_ref: firestore.DocumentReference,
    caller_uid: str,
    action: str,
    reason: str,
    target_analyst_id: str | None,
    updates: dict[str, object],
    audit_event_dict: dict[str, object],
) -> tuple[str, dict[str, object]]:
    snapshot = case_ref.get(transaction=transaction)
    if not snapshot.exists:
        return "not_found", {}
    document = snapshot.to_dict() or {}

    if action in ("CLEAR", "BLOCK_HOLD"):
        if document.get("state") == CaseState.FINALIZED.value:
            identical = (
                document.get("final_disposition") == action
                and document.get("assigned_analyst_id") == caller_uid
                and document.get("final_reason") == reason
            )
            return ("idempotent", document) if identical else ("conflict", document)

        if document.get("state") != CaseState.HUMAN_REVIEW.value or document.get("assigned_analyst_id") != caller_uid:
            return "conflict", document

        transaction.set(case_ref, updates, merge=True)
        transaction.set(audit_ref, audit_event_dict)
        document.update(updates)
        return "applied", document

    # ESCALATE_SENIOR: a reassignment, never a finalization -- state stays
    # HUMAN_REVIEW throughout, so eligibility is judged on ownership, not state.
    if document.get("state") != CaseState.HUMAN_REVIEW.value:
        return "conflict", document

    if document.get("assigned_analyst_id") == caller_uid:
        transaction.set(case_ref, updates, merge=True)
        transaction.set(audit_ref, audit_event_dict)
        document.update(updates)
        return "applied", document

    if document.get("assigned_analyst_id") == target_analyst_id:
        # Ownership already moved to exactly this request's target -- a
        # concurrent duplicate of this same escalation already won; treat as
        # an idempotent replay rather than a conflict.
        return "idempotent", document

    return "conflict", document
