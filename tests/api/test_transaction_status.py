"""Unit tests for GET /transactions/{transaction_id}/status (the Transaction
Console's live pipeline-progress poll target), using an in-memory fake
CaseStore injected via FastAPI's dependency_overrides -- deterministic, no
network dependency. Mirrors the fake-store pattern in tests/api/test_cases.py
and tests/pipeline/test_orchestrator.py.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from services.api.cases import get_case_store
from services.api.main import app


class FakeCaseStore:
    """In-memory double implementing only the two CaseStore methods this
    endpoint calls."""

    def __init__(self) -> None:
        self.transactions: dict[str, str] = {}
        self.cases: dict[str, dict[str, object]] = {}

    def seed(self, transaction_id: str, case_id: str, document: dict[str, object]) -> None:
        self.transactions[transaction_id] = case_id
        self.cases[case_id] = dict(document)

    def get_case_id_for_transaction(self, transaction_id: str):
        return self.transactions.get(transaction_id)

    def get_case(self, case_id: str):
        return self.cases.get(case_id)


def _client(store: FakeCaseStore) -> TestClient:
    app.dependency_overrides[get_case_store] = lambda: store
    return TestClient(app)


def test_no_case_yet_returns_all_null_not_404():
    store = FakeCaseStore()
    client = _client(store)

    response = client.get("/transactions/tx_not_started/status")

    assert response.status_code == 200
    assert response.json() == {
        "case_id": None,
        "state": None,
        "has_evidence_bundle": False,
        "has_robustness": False,
        "has_policy_decision": False,
    }
    app.dependency_overrides.clear()


def test_reports_detected_state_with_no_downstream_artifacts_yet():
    store = FakeCaseStore()
    store.seed("tx_1", "case_1", {"state": "DETECTED"})
    client = _client(store)

    response = client.get("/transactions/tx_1/status")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "case_1"
    assert body["state"] == "DETECTED"
    assert body["has_evidence_bundle"] is False
    assert body["has_robustness"] is False
    assert body["has_policy_decision"] is False
    app.dependency_overrides.clear()


def test_reports_each_downstream_artifact_as_it_lands():
    store = FakeCaseStore()
    store.seed(
        "tx_2",
        "case_2",
        {
            "state": "POLICY_EVALUATED",
            "evidence_bundle": {"completeness": "COMPLETE"},
            "robustness": {"classification": "ROBUST"},
            "policy_decision": {"rule_id": "P-002", "outcome": "ESCALATE"},
        },
    )
    client = _client(store)

    response = client.get("/transactions/tx_2/status")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "case_2"
    assert body["state"] == "POLICY_EVALUATED"
    assert body["has_evidence_bundle"] is True
    assert body["has_robustness"] is True
    assert body["has_policy_decision"] is True
    app.dependency_overrides.clear()


def test_never_exposes_protected_case_content_only_booleans():
    store = FakeCaseStore()
    store.seed(
        "tx_3",
        "case_3",
        {
            "state": "EVIDENCE_READY",
            "evidence_bundle": {"facts": ["protected fact content"], "completeness": "COMPLETE"},
        },
    )
    client = _client(store)

    response = client.get("/transactions/tx_3/status")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"case_id", "state", "has_evidence_bundle", "has_robustness", "has_policy_decision"}
    assert "protected fact content" not in response.text
    app.dependency_overrides.clear()
