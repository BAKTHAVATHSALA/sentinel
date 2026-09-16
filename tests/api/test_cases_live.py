"""Phase 5.1 + Phase B/D/E real-Firestore, real-Firebase-Auth integration
tests for the Case API.

Signs in as the real, live Firebase demo accounts created for this project
(README's Authentication section documents how they were provisioned) via
the Identity Toolkit REST API's signInWithPassword, exactly as the analyst
UI's browser-side Firebase SDK does -- so this test exercises the real
`Authorization: Bearer <id_token>` path through shared/auth/dependencies.py,
not a mocked token. Seeds a real case document directly via CaseStore,
exercises GET /cases, GET /cases/{case_id}, and POST /cases/{case_id}/decision
through the real FastAPI app with the real Firestore-backed dependencies,
then cleans up.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import uuid

import httpx
import pytest
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

# Real Firebase Web API key for the sentinel-ai-builder-cup project (public by
# design -- it identifies the project for the Identity Toolkit REST API; it
# is not a secret credential, security is enforced by Firebase Auth +
# Firestore rules, not by hiding this value). Mirrors ui/src/lib/firebase.ts.
FIREBASE_API_KEY = "AIzaSyCb2GMJ-WPkC7NXnM2ZDrn6bRRwkH7nBWA"
DEMO_PASSWORD = "SentinelDemo!2026"

ANALYST_1_UID = "Kf7TBulMUnX9xOQYs6hNK9IBmTO2"  # analyst1@sentinel.demo
SENIOR_1_UID = "kyDqtXKjN3S9DChS3Qy7qEGE5Lz2"  # senior1@sentinel.demo


def _sign_in(email: str, password: str = DEMO_PASSWORD) -> str:
    """Real Firebase email/password sign-in, exactly what the browser-side
    Firebase SDK does -- returns a real, verifiable ID token."""
    response = httpx.post(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        params={"key": FIREBASE_API_KEY},
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["idToken"]


@pytest.fixture(scope="module")
def analyst_token() -> str:
    return _sign_in("analyst1@sentinel.demo")


@pytest.fixture(scope="module")
def senior_token() -> str:
    return _sign_in("senior1@sentinel.demo")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


def _seed_human_review_case(store: CaseStore, case_id: str, transaction_id: str, assigned_analyst_id: str) -> None:
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
        assigned_analyst_id=assigned_analyst_id,
    )
    created, _ = store.create_case_if_new(transaction_id, case_id, document)
    assert created is True


def _cleanup(store: CaseStore, case_id: str, transaction_id: str) -> None:
    for doc in store._client.collection(store._cases_collection).document(case_id).collection(
        store._audit_collection
    ).stream():
        doc.reference.delete()
    store._client.collection(store._cases_collection).document(case_id).delete()
    store._client.collection(store._transactions_collection).document(transaction_id).delete()


def test_unauthenticated_request_is_rejected() -> None:
    client = TestClient(app)
    response = client.get("/cases")
    assert response.status_code == 401


def test_live_queue_scoped_to_real_authenticated_analyst(analyst_token: str) -> None:
    suffix = uuid.uuid4().hex[:8]
    case_id, transaction_id = f"case_live_api_{suffix}", f"tx_live_api_{suffix}"
    store = CaseStore(build_firestore_client())
    client = TestClient(app)

    try:
        _seed_human_review_case(store, case_id, transaction_id, ANALYST_1_UID)

        list_response = client.get("/cases", headers=_auth_headers(analyst_token))
        assert list_response.status_code == 200
        matching = [row for row in list_response.json() if row["case_id"] == case_id]
        assert len(matching) == 1
        assert matching[0]["risk_band"] == "HIGH"
        assert matching[0]["robustness_classification"] == "ROBUST"

        detail_response = client.get(f"/cases/{case_id}", headers=_auth_headers(analyst_token))
        assert detail_response.status_code == 200
        assert detail_response.json()["state"] == "HUMAN_REVIEW"
        assert detail_response.json()["available_seniors"][0]["uid"] == SENIOR_1_UID
    finally:
        _cleanup(store, case_id, transaction_id)


def test_live_escalation_then_senior_sees_it_and_finalizes(analyst_token: str, senior_token: str) -> None:
    suffix = uuid.uuid4().hex[:8]
    case_id, transaction_id = f"case_live_esc_{suffix}", f"tx_live_esc_{suffix}"
    store = CaseStore(build_firestore_client())
    client = TestClient(app)

    try:
        _seed_human_review_case(store, case_id, transaction_id, ANALYST_1_UID)

        escalate_response = client.post(
            f"/cases/{case_id}/decision",
            headers=_auth_headers(analyst_token),
            json={
                "case_id": case_id,
                "analyst_id": ANALYST_1_UID,
                "action": "ESCALATE_SENIOR",
                "reason": "Needs a second opinion on the linked-account signal",
                "evidence_acknowledged": True,
                "client_timestamp": NOW.isoformat(),
                "target_analyst_id": SENIOR_1_UID,
            },
        )
        assert escalate_response.status_code == 200
        assert escalate_response.json()["state"] == "HUMAN_REVIEW"
        assert escalate_response.json()["assigned_analyst_id"] == SENIOR_1_UID

        # The original analyst no longer sees it in their queue.
        analyst_queue = client.get("/cases", headers=_auth_headers(analyst_token))
        assert case_id not in [row["case_id"] for row in analyst_queue.json()]

        # The senior now sees it -- and cannot escalate further.
        senior_queue = client.get("/cases", headers=_auth_headers(senior_token))
        assert case_id in [row["case_id"] for row in senior_queue.json()]

        senior_escalate_attempt = client.post(
            f"/cases/{case_id}/decision",
            headers=_auth_headers(senior_token),
            json={
                "case_id": case_id,
                "analyst_id": SENIOR_1_UID,
                "action": "ESCALATE_SENIOR",
                "reason": "trying anyway",
                "evidence_acknowledged": True,
                "client_timestamp": NOW.isoformat(),
                "target_analyst_id": SENIOR_1_UID,
            },
        )
        assert senior_escalate_attempt.status_code == 403

        finalize_response = client.post(
            f"/cases/{case_id}/decision",
            headers=_auth_headers(senior_token),
            json={
                "case_id": case_id,
                "analyst_id": SENIOR_1_UID,
                "action": "CLEAR",
                "reason": "Reviewed the linked-account signal, confirmed legitimate",
                "evidence_acknowledged": True,
                "client_timestamp": NOW.isoformat(),
            },
        )
        assert finalize_response.status_code == 200
        assert finalize_response.json()["final_disposition"] == "CLEAR"

        finalized = store.get_case(case_id)
        assert finalized["state"] == "FINALIZED"
        assert finalized["final_disposition"] == "CLEAR"
    finally:
        _cleanup(store, case_id, transaction_id)
