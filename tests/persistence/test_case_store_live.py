"""Phase 4.2 real-Firestore integration tests for CaseStore.

These hit the real Firestore database for real (Application Default
Credentials, no emulator/fake) -- the Build Checklist and the task
instructions explicitly require Firestore checks to use the real GCP
environment. Each test uses a uniquely-suffixed case_id/transaction_id and
cleans up after itself so repeated runs never collide or leave debris.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from shared.contracts.case import CaseState
from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.events import ActorType, AuditEvent
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
from shared.persistence.case_document import build_case_document
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client

NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)


def _transaction(transaction_id: str) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        customer_id="cust_test",
        account_id="acc_test",
        card_id="card_test",
        merchant_id="merch_test",
        amount=Decimal("42.00"),
        currency="USD",
        timestamp=NOW,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_test",
        ip_address="198.51.100.1",
        geo=Geo(lat=Decimal("40.7128"), lon=Decimal("-74.0060"), country="USA"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )


def _detection(case_id: str, transaction_id: str) -> DetectionOutput:
    return DetectionOutput(
        case_id=case_id,
        transaction_id=transaction_id,
        risk_score=Decimal("0.10"),
        risk_band=RiskBand.LOW,
        anomaly_tags=[AnomalyTag.NEW_DEVICE],
        detection_reasons=["test"],
        model_name="test-model",
        model_version="v0",
        detected_at=NOW,
    )


def _store() -> CaseStore:
    return CaseStore(build_firestore_client())


def test_live_create_case_if_new_creates_exactly_once() -> None:
    suffix = uuid.uuid4().hex[:8]
    transaction_id = f"tx_live_{suffix}"
    case_id = f"case_live_{suffix}"
    store = _store()

    document = build_case_document(
        case_id=case_id,
        transaction_id=transaction_id,
        state=CaseState.DETECTED,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(transaction_id),
        detection=_detection(case_id, transaction_id),
    )
    try:
        created, resolved_case_id = store.create_case_if_new(transaction_id, case_id, document)
        assert created is True
        assert resolved_case_id == case_id

        fetched = store.get_case(case_id)
        assert fetched is not None
        assert fetched["case_id"] == case_id
        assert fetched["state"] == "DETECTED"

        assert store.get_case_id_for_transaction(transaction_id) == case_id
    finally:
        store._client.collection(store._cases_collection).document(case_id).delete()
        store._client.collection(store._transactions_collection).document(transaction_id).delete()


def test_live_duplicate_transaction_id_does_not_create_a_second_case() -> None:
    """Safety Invariants 8/9: duplicate delivery for the same transaction_id must not
    create a second independent case."""
    suffix = uuid.uuid4().hex[:8]
    transaction_id = f"tx_live_dup_{suffix}"
    first_case_id = f"case_live_dup_first_{suffix}"
    second_case_id = f"case_live_dup_second_{suffix}"
    store = _store()

    first_doc = build_case_document(
        case_id=first_case_id,
        transaction_id=transaction_id,
        state=CaseState.DETECTED,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(transaction_id),
        detection=_detection(first_case_id, transaction_id),
    )
    second_doc = build_case_document(
        case_id=second_case_id,
        transaction_id=transaction_id,
        state=CaseState.DETECTED,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(transaction_id),
        detection=_detection(second_case_id, transaction_id),
    )
    try:
        created_1, resolved_1 = store.create_case_if_new(transaction_id, first_case_id, first_doc)
        created_2, resolved_2 = store.create_case_if_new(transaction_id, second_case_id, second_doc)

        assert created_1 is True
        assert created_2 is False
        assert resolved_1 == first_case_id
        assert resolved_2 == first_case_id  # duplicate resolves back to the original case

        assert store.get_case(second_case_id) is None  # second case was never written
        assert store.get_case(first_case_id) is not None
    finally:
        store._client.collection(store._cases_collection).document(first_case_id).delete()
        store._client.collection(store._cases_collection).document(second_case_id).delete()
        store._client.collection(store._transactions_collection).document(transaction_id).delete()


def test_live_update_case_merges_fields() -> None:
    suffix = uuid.uuid4().hex[:8]
    transaction_id = f"tx_live_upd_{suffix}"
    case_id = f"case_live_upd_{suffix}"
    store = _store()

    document = build_case_document(
        case_id=case_id,
        transaction_id=transaction_id,
        state=CaseState.DETECTED,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(transaction_id),
        detection=_detection(case_id, transaction_id),
    )
    try:
        store.create_case_if_new(transaction_id, case_id, document)
        store.update_case(case_id, {"state": CaseState.AUTO_RESOLVED.value})

        fetched = store.get_case(case_id)
        assert fetched is not None
        assert fetched["state"] == "AUTO_RESOLVED"
        assert fetched["transaction_id"] == transaction_id  # untouched fields survive the merge
    finally:
        store._client.collection(store._cases_collection).document(case_id).delete()
        store._client.collection(store._transactions_collection).document(transaction_id).delete()


def test_live_append_audit_event_writes_to_subcollection() -> None:
    suffix = uuid.uuid4().hex[:8]
    transaction_id = f"tx_live_audit_{suffix}"
    case_id = f"case_live_audit_{suffix}"
    store = _store()

    document = build_case_document(
        case_id=case_id,
        transaction_id=transaction_id,
        state=CaseState.DETECTED,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(transaction_id),
        detection=_detection(case_id, transaction_id),
    )
    audit_event = AuditEvent(
        audit_event_id=f"aud_{suffix}",
        case_id=case_id,
        transaction_id=transaction_id,
        event_type="CASE_DETECTED",
        actor_type=ActorType.SYSTEM,
        occurred_at=NOW,
    )
    try:
        store.create_case_if_new(transaction_id, case_id, document)
        store.append_audit_event(case_id, audit_event)

        subcollection_docs = list(
            store._client.collection(store._cases_collection)
            .document(case_id)
            .collection(store._audit_collection)
            .stream()
        )
        assert len(subcollection_docs) == 1
        assert subcollection_docs[0].id == audit_event.audit_event_id
        assert subcollection_docs[0].to_dict()["event_type"] == "CASE_DETECTED"
    finally:
        store._client.collection(store._cases_collection).document(case_id).collection(
            store._audit_collection
        ).document(audit_event.audit_event_id).delete()
        store._client.collection(store._cases_collection).document(case_id).delete()
        store._client.collection(store._transactions_collection).document(transaction_id).delete()
