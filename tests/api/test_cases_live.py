"""Phase 5.1 real-Firestore integration tests for the Case API.

Seeds a real case document directly via CaseStore, exercises GET /cases,
GET /cases/{case_id}, and POST /cases/{case_id}/decision through the real
FastAPI app with the real Firestore-backed dependency, then cleans up.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from fastapi.testclient import TestClient

from services.api.main import app
from shared.contracts.case import CaseState
from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.robustness import RobustnessClassification, RobustnessMethod, RobustnessResult
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
from shared.persistence.case_document import build_case_document
from shared.persistence.case_store import CaseStore
from shared.persistence.firestore_client import build_firestore_client

NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)


def _transaction(transaction_id: str) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        customer_id="cust_test",
        account_id="acc_test",
        card_id="card_test",
        merchant_id="merch_test",
        amount=Decimal("250.00"),
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


def test_live_queue_detail_and_decision_round_trip() -> None:
    suffix = uuid.uuid4().hex[:8]
    case_id = f"case_live_api_{suffix}"
    transaction_id = f"tx_live_api_{suffix}"
    store = CaseStore(build_firestore_client())
    client = TestClient(app)

    detection = DetectionOutput(
        case_id=case_id,
        transaction_id=transaction_id,
        risk_score=Decimal("0.90"),
        risk_band=RiskBand.HIGH,
        anomaly_tags=[AnomalyTag.LINKED_ENTITY_ANOMALY],
        detection_reasons=["test"],
        model_name="test-model",
        model_version="v0",
        detected_at=NOW,
    )
    robustness = RobustnessResult(
        robustness_id=f"rob_{case_id}",
        case_id=case_id,
        classification=RobustnessClassification.ROBUST,
        fragile_factor_id=None,
        method=RobustnessMethod.FAST_PATH,
        evaluated_at=NOW,
    )
    document = build_case_document(
        case_id=case_id,
        transaction_id=transaction_id,
        state=CaseState.HUMAN_REVIEW,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(transaction_id),
        detection=detection,
        robustness=robustness,
    )

    try:
        created, _ = store.create_case_if_new(transaction_id, case_id, document)
        assert created is True

        list_response = client.get("/cases")
        assert list_response.status_code == 200
        matching = [row for row in list_response.json() if row["case_id"] == case_id]
        assert len(matching) == 1
        assert matching[0]["risk_band"] == "HIGH"
        assert matching[0]["robustness_classification"] == "ROBUST"

        detail_response = client.get(f"/cases/{case_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["state"] == "HUMAN_REVIEW"

        decision_response = client.post(
            f"/cases/{case_id}/decision",
            json={
                "case_id": case_id,
                "analyst_id": "analyst_live_test",
                "action": "ESCALATE_SENIOR",
                "reason": "Needs a second opinion on the linked-account signal",
                "evidence_acknowledged": True,
                "client_timestamp": NOW.isoformat(),
            },
        )
        assert decision_response.status_code == 200
        assert decision_response.json()["final_disposition"] == "ESCALATE_SENIOR"

        finalized = store.get_case(case_id)
        assert finalized["state"] == "FINALIZED"
        assert finalized["final_disposition"] == "ESCALATE_SENIOR"

        # Now finalized -- no longer in the review queue.
        list_after = client.get("/cases")
        assert case_id not in [row["case_id"] for row in list_after.json()]
    finally:
        for doc in store._client.collection(store._cases_collection).document(case_id).collection(
            store._audit_collection
        ).stream():
            doc.reference.delete()
        store._client.collection(store._cases_collection).document(case_id).delete()
        store._client.collection(store._transactions_collection).document(transaction_id).delete()
