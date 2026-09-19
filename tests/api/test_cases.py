"""Unit tests for the Build Checklist Phase 5.1 Case API, using an in-memory
fake CaseStore/AnalystDirectory and a stubbed authenticated caller injected
via FastAPI's dependency_overrides -- deterministic, no network dependency.
The real Firestore/Firebase integration is covered separately by
tests/api/test_cases_live.py."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from services.api.cases import get_case_store, get_reasoning_client
from services.api.main import app
from shared.auth.dependencies import get_analyst_directory, get_current_analyst
from shared.auth.models import AnalystRecord, AnalystRole, AuthenticatedAnalyst
from shared.contracts.case import CaseState
from shared.persistence.case_document import build_case_document
from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.robustness import RobustnessClassification, RobustnessMethod, RobustnessResult
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction

NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)

ANALYST_UID = "uid_analyst_a"
OTHER_ANALYST_UID = "uid_analyst_b"
SENIOR_UID = "uid_senior_a"


class FakeCaseStore:
    """In-memory double implementing CaseStore's public surface used by the API,
    including the first-valid-decision-wins transactional method."""

    def __init__(self) -> None:
        self.cases: dict[str, dict[str, object]] = {}
        self.audit_events: dict[str, list[dict[str, object]]] = {}

    def seed(self, case_id: str, document: dict[str, object]) -> None:
        self.cases[case_id] = dict(document)
        self.audit_events[case_id] = []

    def list_cases_by_state_and_assigned_analyst(self, state: str, assigned_analyst_id: str) -> list[dict[str, object]]:
        return [c for c in self.cases.values() if c["state"] == state and c.get("assigned_analyst_id") == assigned_analyst_id]

    def get_case(self, case_id: str):
        return self.cases.get(case_id)

    def update_case(self, case_id: str, updates: dict[str, object]) -> None:
        self.cases[case_id].update(updates)

    def append_audit_event(self, case_id: str, audit_event) -> None:
        self.audit_events.setdefault(case_id, []).append(audit_event.model_dump(mode="json"))

    def apply_human_decision(self, case_id, caller_uid, action, reason, target_analyst_id, updates, audit_event):
        document = self.cases.get(case_id)
        if document is None:
            return "not_found", {}

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
            document.update(updates)
            self.audit_events.setdefault(case_id, []).append(audit_event.model_dump(mode="json"))
            return "applied", document

        if document.get("state") != CaseState.HUMAN_REVIEW.value:
            return "conflict", document
        if document.get("assigned_analyst_id") == caller_uid:
            document.update(updates)
            self.audit_events.setdefault(case_id, []).append(audit_event.model_dump(mode="json"))
            return "applied", document
        if document.get("assigned_analyst_id") == target_analyst_id:
            return "idempotent", document
        return "conflict", document


class FakeAnalystDirectory:
    def __init__(self, records: dict[str, AnalystRecord] | None = None) -> None:
        self._records = records or {
            SENIOR_UID: AnalystRecord(
                uid=SENIOR_UID, email="senior@sentinel.demo", display_name="Test Senior",
                role=AnalystRole.SENIOR_ANALYST, active=True,
            ),
        }

    def get(self, uid: str) -> AnalystRecord | None:
        return self._records.get(uid)

    def list_active_seniors(self) -> list[AnalystRecord]:
        return [r for r in self._records.values() if r.role == AnalystRole.SENIOR_ANALYST and r.active]


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


def _human_review_case(case_id: str = "case_api_test", assigned_analyst_id: str = ANALYST_UID) -> dict[str, object]:
    robustness = RobustnessResult(
        robustness_id=f"rob_{case_id}",
        case_id=case_id,
        classification=RobustnessClassification.FRAGILE,
        fragile_factor_id="fact_01",
        method=RobustnessMethod.FAST_PATH,
        evaluated_at=NOW,
    )
    doc = build_case_document(
        case_id=case_id,
        transaction_id="tx_api_test",
        state=CaseState.HUMAN_REVIEW,
        created_at=NOW,
        updated_at=NOW,
        transaction=_transaction(),
        detection=_detection(),
        robustness=robustness,
        assigned_analyst_id=assigned_analyst_id,
    )
    return doc


@pytest.fixture()
def fake_store() -> FakeCaseStore:
    store = FakeCaseStore()
    app.dependency_overrides[get_case_store] = lambda: store
    yield store
    app.dependency_overrides.pop(get_case_store, None)


@pytest.fixture()
def fake_directory() -> FakeAnalystDirectory:
    directory = FakeAnalystDirectory()
    app.dependency_overrides[get_analyst_directory] = lambda: directory
    yield directory
    app.dependency_overrides.pop(get_analyst_directory, None)


def _as(uid: str, role: AnalystRole = AnalystRole.ANALYST):
    caller = AuthenticatedAnalyst(uid=uid, email=f"{uid}@sentinel.demo", display_name=uid, role=role)
    app.dependency_overrides[get_current_analyst] = lambda: caller
    return caller


@pytest.fixture(autouse=True)
def _clear_caller_override():
    yield
    app.dependency_overrides.pop(get_current_analyst, None)
    app.dependency_overrides.pop(get_reasoning_client, None)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# --- authentication ---


def test_cases_requires_authentication(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    response = client.get("/cases")
    assert response.status_code == 401


# --- queue scoping (Phase E) ---


def test_list_cases_scoped_to_caller_only(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_mine", _human_review_case("case_mine", assigned_analyst_id=ANALYST_UID))
    fake_store.seed("case_other", _human_review_case("case_other", assigned_analyst_id=OTHER_ANALYST_UID))
    _as(ANALYST_UID)

    response = client.get("/cases")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["case_id"] == "case_mine"


def test_analyst_a_cannot_see_analyst_b_cases_in_queue(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_b", _human_review_case("case_b", assigned_analyst_id=OTHER_ANALYST_UID))
    _as(ANALYST_UID)

    response = client.get("/cases")

    assert response.json() == []


def test_auto_resolve_cases_never_exposed_as_analyst_work(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    case = _human_review_case("case_auto", assigned_analyst_id=ANALYST_UID)
    case["state"] = CaseState.AUTO_RESOLVED.value
    fake_store.seed("case_auto", case)
    _as(ANALYST_UID)

    response = client.get("/cases")

    assert response.json() == []


def test_senior_only_sees_cases_assigned_to_that_senior(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_escalated", _human_review_case("case_escalated", assigned_analyst_id=SENIOR_UID))
    _as(SENIOR_UID, role=AnalystRole.SENIOR_ANALYST)

    response = client.get("/cases")

    assert len(response.json()) == 1


# --- case detail scoping ---


def test_get_case_returns_full_document_when_assigned_to_caller(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.get("/cases/case_api_test")

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "case_api_test"
    assert body["transaction"]["amount"] == "120.00"
    assert "available_seniors" in body
    assert body["available_seniors"][0]["email"] == "senior@sentinel.demo"


def test_get_case_404_when_not_assigned_to_caller(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    """Q11 consistency fix: a case that exists but isn't yours returns the
    same 404 as a case that doesn't exist at all -- never 403 -- so neither
    the frontend nor an external observer can tell the two apart."""
    fake_store.seed("case_api_test", _human_review_case(assigned_analyst_id=OTHER_ANALYST_UID))
    _as(ANALYST_UID)

    response = client.get("/cases/case_api_test")

    assert response.status_code == 404


def test_get_case_404_when_missing(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    _as(ANALYST_UID)
    response = client.get("/cases/does_not_exist")
    assert response.status_code == 404


def test_get_case_not_found_and_not_assigned_use_the_identical_message_template(
    client: TestClient, fake_store: FakeCaseStore, fake_directory
) -> None:
    """The actual proof, not just matching status codes: both failure modes
    use the identical "Case '<id>' not found" template -- the case_id each
    response echoes back is not new information (the caller already put it
    in the URL), but neither response may say anything that distinguishes
    "doesn't exist" from "exists but isn't yours" (e.g. no "assigned"/"403"
    wording anywhere)."""
    fake_store.seed("case_api_test", _human_review_case(assigned_analyst_id=OTHER_ANALYST_UID))
    _as(ANALYST_UID)

    not_assigned_response = client.get("/cases/case_api_test")
    not_found_response = client.get("/cases/does_not_exist")

    assert not_assigned_response.status_code == not_found_response.status_code == 404
    assert not_assigned_response.json()["detail"] == "Case 'case_api_test' not found"
    assert not_found_response.json()["detail"] == "Case 'does_not_exist' not found"
    assert "assigned" not in not_assigned_response.json()["detail"].lower()


def test_get_case_response_includes_analyst_identity_headers(
    client: TestClient, fake_store: FakeCaseStore, fake_directory
) -> None:
    """Additive response headers (not a new endpoint, not a body-shape
    change) so the frontend's persistent nav bar can show the caller's own
    display name/role without a dedicated "who am I" endpoint."""
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.get("/cases/case_api_test")

    assert response.headers["X-Analyst-Display-Name"] == ANALYST_UID  # _as() sets display_name=uid
    assert response.headers["X-Analyst-Role"] == "ANALYST"


def test_list_cases_response_includes_analyst_identity_headers(
    client: TestClient, fake_store: FakeCaseStore, fake_directory
) -> None:
    _as(SENIOR_UID, role=AnalystRole.SENIOR_ANALYST)

    response = client.get("/cases")

    assert response.headers["X-Analyst-Display-Name"] == SENIOR_UID
    assert response.headers["X-Analyst-Role"] == "SENIOR_ANALYST"


# --- human decisions ---


def _decision_payload(action: str, reason: str | None, analyst_id: str = ANALYST_UID, target_analyst_id: str | None = None, evidence_acknowledged: bool = True) -> dict[str, object]:
    return {
        "case_id": "case_api_test",
        "analyst_id": analyst_id,
        "action": action,
        "reason": reason,
        "evidence_acknowledged": evidence_acknowledged,
        "client_timestamp": NOW.isoformat(),
        "target_analyst_id": target_analyst_id,
    }


def test_decision_clear_succeeds_and_finalizes(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", "Reviewed, legitimate purchase"))

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "FINALIZED"
    assert body["final_disposition"] == "CLEAR"
    assert body["idempotent_replay"] is False
    assert body["target_analyst_display_name"] is None  # only ever set for ESCALATE_SENIOR
    assert fake_store.cases["case_api_test"]["state"] == "FINALIZED"
    assert fake_store.audit_events["case_api_test"][-1]["actor_type"] == "HUMAN"
    assert fake_store.audit_events["case_api_test"][-1]["actor_id"] == ANALYST_UID


def test_decision_clear_requires_reason_now_mandatory(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    """V1 Authoritative Ruling Part 7: CLEAR's reason is mandatory, not optional."""
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", None))

    assert response.status_code == 400
    assert fake_store.cases["case_api_test"]["state"] == "HUMAN_REVIEW"


def test_decision_block_hold_requires_reason(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post("/cases/case_api_test/decision", json=_decision_payload("BLOCK_HOLD", None))

    assert response.status_code == 400


def test_decision_block_hold_with_reason_succeeds(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post(
        "/cases/case_api_test/decision", json=_decision_payload("BLOCK_HOLD", "Confirmed fraud pattern")
    )

    assert response.status_code == 200
    assert response.json()["final_disposition"] == "BLOCK_HOLD"


def test_decision_requires_evidence_acknowledged(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post(
        "/cases/case_api_test/decision", json=_decision_payload("CLEAR", "reason", evidence_acknowledged=False)
    )

    assert response.status_code == 400


def test_decision_analyst_id_mismatch_rejected(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    """V1 Authoritative Ruling Part 1: never trust analyst_id from the client --
    reject when it doesn't match the verified caller."""
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post(
        "/cases/case_api_test/decision", json=_decision_payload("CLEAR", "reason", analyst_id="someone_else")
    )

    assert response.status_code == 403


def test_decision_404_when_case_missing(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    _as(ANALYST_UID)
    payload = _decision_payload("CLEAR", "reason")
    payload["case_id"] = "does_not_exist"

    response = client.post("/cases/does_not_exist/decision", json=payload)

    assert response.status_code == 404


def test_decision_path_case_id_must_match_body(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)
    payload = _decision_payload("CLEAR", "reason")
    payload["case_id"] = "some_other_case"

    response = client.post("/cases/case_api_test/decision", json=payload)

    assert response.status_code == 400


def test_decision_403_when_case_not_assigned_to_caller(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case(assigned_analyst_id=OTHER_ANALYST_UID))
    _as(ANALYST_UID)

    response = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", "reason"))

    assert response.status_code == 403


# --- concurrency / idempotency (V1 Authoritative Ruling Part 8) ---


def test_decision_is_idempotent_on_identical_replay(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)
    first = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", "same reason"))
    assert first.status_code == 200
    audit_count_after_first = len(fake_store.audit_events["case_api_test"])

    second = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", "same reason"))

    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert len(fake_store.audit_events["case_api_test"]) == audit_count_after_first


def test_conflicting_later_decision_is_rejected_first_valid_wins(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)
    first = client.post("/cases/case_api_test/decision", json=_decision_payload("CLEAR", "cleared it"))
    assert first.status_code == 200

    second = client.post("/cases/case_api_test/decision", json=_decision_payload("BLOCK_HOLD", "actually block it"))

    assert second.status_code == 409
    # Final disposition was never overwritten by the losing request.
    assert fake_store.cases["case_api_test"]["final_disposition"] == "CLEAR"


# --- escalation (Phase D) ---


def test_analyst_can_escalate_to_valid_senior(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post(
        "/cases/case_api_test/decision",
        json=_decision_payload("ESCALATE_SENIOR", "needs senior judgment", target_analyst_id=SENIOR_UID),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "HUMAN_REVIEW"  # Addendum 1 Point 1: not finalized
    assert body["assigned_analyst_id"] == SENIOR_UID
    # Q11 verification fix: the response carries the senior's real display
    # name, sourced from the already-validated directory record -- the
    # frontend's escalation confirmation never needs to call GET /cases/{id}.
    assert body["target_analyst_display_name"] == "Test Senior"
    assert fake_store.cases["case_api_test"]["state"] == CaseState.HUMAN_REVIEW.value


def test_escalation_requires_reason(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post(
        "/cases/case_api_test/decision",
        json=_decision_payload("ESCALATE_SENIOR", None, target_analyst_id=SENIOR_UID),
    )

    assert response.status_code == 400


def test_senior_cannot_escalate(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case(assigned_analyst_id=SENIOR_UID))
    _as(SENIOR_UID, role=AnalystRole.SENIOR_ANALYST)

    response = client.post(
        "/cases/case_api_test/decision",
        json=_decision_payload("ESCALATE_SENIOR", "trying anyway", analyst_id=SENIOR_UID, target_analyst_id=SENIOR_UID),
    )

    assert response.status_code == 403


def test_escalation_target_must_be_a_valid_active_senior(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post(
        "/cases/case_api_test/decision",
        json=_decision_payload("ESCALATE_SENIOR", "needs senior judgment", target_analyst_id="not_a_real_senior"),
    )

    assert response.status_code == 400


def test_escalation_target_must_be_senior_not_another_analyst(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_directory._records[OTHER_ANALYST_UID] = AnalystRecord(
        uid=OTHER_ANALYST_UID, email="b@sentinel.demo", display_name="B", role=AnalystRole.ANALYST, active=True
    )
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)

    response = client.post(
        "/cases/case_api_test/decision",
        json=_decision_payload("ESCALATE_SENIOR", "wrong target", target_analyst_id=OTHER_ANALYST_UID),
    )

    assert response.status_code == 400


def test_duplicate_escalation_replay_is_idempotent(client: TestClient, fake_store: FakeCaseStore, fake_directory) -> None:
    fake_store.seed("case_api_test", _human_review_case())
    _as(ANALYST_UID)
    first = client.post(
        "/cases/case_api_test/decision",
        json=_decision_payload("ESCALATE_SENIOR", "needs senior judgment", target_analyst_id=SENIOR_UID),
    )
    assert first.status_code == 200

    # The original analyst retries their own already-applied escalation
    # (e.g. a network retry) -- ownership already moved to the senior, but
    # this must still be recognized as an idempotent replay, not a conflict.
    second = client.post(
        "/cases/case_api_test/decision",
        json=_decision_payload("ESCALATE_SENIOR", "needs senior judgment", target_analyst_id=SENIOR_UID),
    )

    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True


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
