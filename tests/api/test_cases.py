"""Unit tests for the Build Checklist Phase 5.1 Case API, using an in-memory
fake CaseStore injected via FastAPI's dependency_overrides -- deterministic,
no network dependency. The real Firestore integration is covered separately
by tests/api/test_cases_live.py."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from services.api.cases import get_case_store
from services.api.main import app
from shared.contracts.case import CaseState
from shared.persistence.case_document import build_case_document
from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.robustness import RobustnessClassification, RobustnessMethod, RobustnessResult
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction

NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)


class FakeCaseStore:
    """In-memory double implementing CaseStore's public surface used by the API."""

    def __init__(self) -> None:
        self.cases: dict[str, dict[str, object]] = {}
        self.audit_events: dict[str, list[dict[str, object]]] = {}

    def seed(self, case_id: str, document: dict[str, object]) -> None:
        self.cases[case_id] = dict(document)
        self.audit_events[case_id] = []

    def list_cases_by_state(self, state: str) -> list[dict[str, object]]:
        return [c for c in self.cases.values() if c["state"] == state]

    def get_case(self, case_id: str):
        return self.cases.get(case_id)

    def update_case(self, case_id: str, updates: dict[str, object]) -> None:
        self.cases[case_id].update(updates)

    def append_audit_event(self, case_id: str, audit_event) -> None:
        self.audit_events[case_id].append(audit_event.model_dump(mode="json"))


def _transaction() -> Transaction:
    return Transaction(
        transaction_id="tx_api_test",
        customer_id="cust_test",
        account_id="acc_test",
        card_id="card_test",
        merchant_id="merch_test",
        amount=Decimal("120.00"),
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


def _detection() -> DetectionOutput:
    return DetectionOutput(
        case_id="case_api_test",
        transaction_id="tx_api_test",
        risk_score=Decimal("0.90"),
        risk_band=RiskBand.HIGH,
        anomaly_tags=[AnomalyTag.MERCHANT_RISK],
        detection_reasons=["test"],
        model_name="test-model",
        model_version="v0",
        detected_at=NOW,
    )


def _human_review_case(case_id: str = "case_api_test") -> dict[str, object]:
    robustness = RobustnessResult(
        robustness_id=f"rob_{case_id}",
        case_id=case_id,
        classification=RobustnessClassification.FRAGILE,
        fragile_factor_id="fact_01",
        method=RobustnessMethod.FAST_PATH,
        evaluated_at=NOW,
    )
    return build_case_document(
        case_id=case_id,
        transaction_id="tx_api_test",
        state=CaseState.HUMAN_REVIEW,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(),
        detection=_detection(),
        robustness=robustness,
    )


@pytest.fixture()
def fake_store() -> FakeCaseStore:
    store = FakeCaseStore()
    app.dependency_overrides[get_case_store] = lambda: store
    yield store
    app.dependency_overrides.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_list_cases_returns_only_human_review_cases(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_open", _human_review_case("case_open"))
    finalized = _human_review_case("case_done")
    finalized["state"] = CaseState.FINALIZED.value
    fake_store.seed("case_done", finalized)

    response = client.get("/cases")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["case_id"] == "case_open"
    assert body[0]["risk_band"] == "HIGH"
    assert body[0]["robustness_classification"] == "FRAGILE"
    assert body[0]["robustness_fragile_factor_id"] == "fact_01"
    assert body[0]["anomaly_tags"] == ["MERCHANT_RISK"]


def test_get_case_returns_full_document(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_api_test", _human_review_case())

    response = client.get("/cases/case_api_test")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "case_api_test"
    assert body["transaction"]["amount"] == "120.00"
    assert body["findings"] is None
    assert body["policy_decision"] is None


def test_get_case_404_when_missing(client: TestClient, fake_store: FakeCaseStore) -> None:
    response = client.get("/cases/does_not_exist")
    assert response.status_code == 404


def _decision_payload(action: str, reason: str | None, evidence_acknowledged: bool = True) -> dict[str, object]:
    return {
        "case_id": "case_api_test",
        "analyst_id": "analyst_42",
        "action": action,
        "reason": reason,
        "evidence_acknowledged": evidence_acknowledged,
        "client_timestamp": NOW.isoformat(),
    }


def test_decision_clear_succeeds_and_finalizes(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_api_test", _human_review_case())

    response = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", None))

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "FINALIZED"
    assert body["final_disposition"] == "CLEAR"
    assert body["idempotent_replay"] is False
    assert fake_store.cases["case_api_test"]["state"] == "FINALIZED"
    assert fake_store.cases["case_api_test"]["final_disposition"] == "CLEAR"
    assert fake_store.audit_events["case_api_test"][-1]["actor_type"] == "HUMAN"
    assert fake_store.audit_events["case_api_test"][-1]["actor_id"] == "analyst_42"


def test_decision_block_hold_requires_reason(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_api_test", _human_review_case())

    response = client.post("/cases/case_api_test/decision", json=_decision_payload("BLOCK_HOLD", None))

    assert response.status_code == 400
    assert fake_store.cases["case_api_test"]["state"] == "HUMAN_REVIEW"  # nothing was applied


def test_decision_block_hold_with_reason_succeeds(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_api_test", _human_review_case())

    response = client.post(
        "/cases/case_api_test/decision", json=_decision_payload("BLOCK_HOLD", "Confirmed fraud pattern")
    )

    assert response.status_code == 200
    assert response.json()["final_disposition"] == "BLOCK_HOLD"


def test_decision_escalate_senior_requires_reason(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_api_test", _human_review_case())

    response = client.post("/cases/case_api_test/decision", json=_decision_payload("ESCALATE_SENIOR", None))

    assert response.status_code == 400


def test_decision_requires_evidence_acknowledged(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_api_test", _human_review_case())

    response = client.post(
        "/cases/case_api_test/decision", json=_decision_payload("CLEAR", None, evidence_acknowledged=False)
    )

    assert response.status_code == 400


def test_decision_rejects_case_not_in_human_review(client: TestClient, fake_store: FakeCaseStore) -> None:
    case = _human_review_case()
    case["state"] = CaseState.EVIDENCE_READY.value
    fake_store.seed("case_api_test", case)

    response = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", None))

    assert response.status_code == 409


def test_decision_404_when_case_missing(client: TestClient, fake_store: FakeCaseStore) -> None:
    payload = _decision_payload("CLEAR", None)
    payload["case_id"] = "does_not_exist"

    response = client.post("/cases/does_not_exist/decision", json=payload)

    assert response.status_code == 404


def test_decision_path_case_id_must_match_body(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    payload = _decision_payload("CLEAR", None)
    payload["case_id"] = "some_other_case"

    response = client.post("/cases/case_api_test/decision", json=payload)

    assert response.status_code == 400


def test_decision_is_idempotent_on_replay(client: TestClient, fake_store: FakeCaseStore) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    first = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", None))
    assert first.status_code == 200
    audit_count_after_first = len(fake_store.audit_events["case_api_test"])

    second = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", None))

    assert second.status_code == 200
    body = second.json()
    assert body["idempotent_replay"] is True
    assert body["final_disposition"] == "CLEAR"
    # No new audit event was written for the replay.
    assert len(fake_store.audit_events["case_api_test"]) == audit_count_after_first


def test_no_code_path_can_set_block_hold_outside_this_endpoint() -> None:
    """Safety Invariant 4: only a human analyst, through this endpoint, may execute
    BLOCK_HOLD. Confirm the literal string appears only as an enum value/comparison
    inside this module, not as a producible outcome anywhere else in shared/pipeline
    or shared/policy (already covered by tests/policy/test_rules.py's AST scan)."""
    import ast
    from pathlib import Path

    pipeline_dir = Path(__file__).resolve().parents[2] / "shared" / "pipeline"
    offenders = []
    for path in pipeline_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "BLOCK_HOLD":
                offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], f"'BLOCK_HOLD' used as a code value in the pipeline: {offenders}"
