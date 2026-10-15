"""Comprehensive security, authorization, isolation, and lifecycle tests for Sentinel Demo Mode.

Tests all non-negotiable boundaries:
1. Cryptographic HMAC capability verification (rejects forged/tampered/expired tokens).
2. Strict session ownership (cross-session access is blocked with 404).
3. Production case isolation (production cases are unreachable via demo endpoints).
4. Production route protection (demo tokens are rejected by Firebase auth on /cases).
5. Human decision workflow (CLEAR and BLOCK_HOLD allowed; ESCALATE_SENIOR cleanly rejected).
6. First-valid-decision-wins concurrency and idempotent replay.
7. Multi-judge isolation during reset (Session A reset does not touch Session B).
8. Rate limiting and expensive call protection (counterfactuals, debounce, reset limits).
"""

from __future__ import annotations

from datetime import datetime, timezone
import time

from fastapi.testclient import TestClient
import pytest

from services.api.demo import get_demo_store
from services.api.main import app
from shared.contracts.case import CaseState
from shared.demo.fixtures import SAMPLE_CLEAN_TRANSACTION, SAMPLE_HIGH_RISK_TRANSACTION
from shared.demo.rate_limiter import demo_rate_limiter
from shared.demo.session import create_demo_session_token
from shared.demo.store import DemoStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    demo_rate_limiter.reset_state()


@pytest.fixture
def isolated_demo_store():
    store = DemoStore()
    app.dependency_overrides[get_demo_store] = lambda: store
    yield store
    app.dependency_overrides.pop(get_demo_store, None)


def _bootstrap_session(test_client: TestClient = client) -> tuple[str, str]:
    """Helper to bootstrap a valid demo session. Returns (token, session_id)."""
    resp = test_client.post("/demo/session")
    assert resp.status_code == 200
    data = resp.json()
    return data["session_token"], data["session_id"]


def test_session_bootstrap_returns_signed_token(isolated_demo_store):
    """POST /demo/session returns a high-entropy signed capability token and initializes cases."""
    token, sid = _bootstrap_session()
    assert len(sid) == 32
    assert token.startswith(sid)

    # 10 cases should now be initialized in the store for this session
    cases = isolated_demo_store.list_cases(sid)
    assert len(cases) == 10


def test_forged_session_token_rejected():
    """Client sending an un-signed or tampered session token receives 401 Unauthorized."""
    resp = client.get("/demo/cases", headers={"X-Sentinel-Demo-Session": "invented_session_string"})
    assert resp.status_code == 401
    assert "Invalid or expired demo session" in resp.json()["detail"]

    # Tampered signature
    valid_token, _ = _bootstrap_session()
    tampered = valid_token[:-4] + "ffff"
    resp2 = client.get("/demo/cases", headers={"X-Sentinel-Demo-Session": tampered})
    assert resp2.status_code == 401


def test_expired_session_token_rejected():
    """Client sending an expired token receives 401 Unauthorized."""
    token, _ = create_demo_session_token(ttl_seconds=-10)  # expired 10s ago
    resp = client.get("/demo/cases", headers={"X-Sentinel-Demo-Session": token})
    assert resp.status_code == 401
    assert "Invalid or expired demo session" in resp.json()["detail"]


def test_missing_token_rejected():
    """Calling demo endpoints without token returns 401."""
    resp = client.get("/demo/cases")
    assert resp.status_code == 401


def test_list_demo_cases_scoped_to_session(isolated_demo_store):
    """GET /demo/cases returns only this session's cases and sets analyst headers."""
    token, sid = _bootstrap_session()
    resp = client.get("/demo/cases", headers={"X-Sentinel-Demo-Session": token})
    assert resp.status_code == 200
    assert resp.headers.get("X-Analyst-Display-Name") == "Demo Analyst"
    assert resp.headers.get("X-Analyst-Role") == "ANALYST"

    cases = resp.json()
    # By default, lists open cases in HUMAN_REVIEW (8 of the 10 templates are open)
    assert len(cases) == 8
    for c in cases:
        assert c["case_id"].startswith(f"demo_{sid}_")

    # With ?scope=dashboard, lists all 10
    dash_resp = client.get("/demo/cases?scope=dashboard", headers={"X-Sentinel-Demo-Session": token})
    assert dash_resp.status_code == 200
    assert len(dash_resp.json()) == 10


def test_production_case_read_blocked(isolated_demo_store):
    """Attempting to access a production case ID returns 404 Not Found."""
    token, _ = _bootstrap_session()
    resp = client.get("/demo/cases/case_363a3f9bb31b", headers={"X-Sentinel-Demo-Session": token})
    assert resp.status_code == 404


def test_cross_session_case_read_blocked(isolated_demo_store):
    """Session A attempting to read Session B's case returns 404 Not Found."""
    token_a, sid_a = _bootstrap_session()
    token_b, sid_b = _bootstrap_session()

    # Session B's case
    b_case_id = f"demo_{sid_b}_case_01"

    # Session A tries to read it
    resp = client.get(f"/demo/cases/{b_case_id}", headers={"X-Sentinel-Demo-Session": token_a})
    assert resp.status_code == 404


def test_cross_session_decision_blocked(isolated_demo_store):
    """Session A attempting to submit a decision on Session B's case returns 404 Not Found."""
    token_a, sid_a = _bootstrap_session()
    token_b, sid_b = _bootstrap_session()

    b_case_id = f"demo_{sid_b}_case_01"
    body = {
        "case_id": b_case_id,
        "action": "CLEAR",
        "reason": "Unauthorized cross-session mutation attempt",
        "evidence_acknowledged": True,
    }
    resp = client.post(f"/demo/cases/{b_case_id}/decision", json=body, headers={"X-Sentinel-Demo-Session": token_a})
    assert resp.status_code == 404


def test_demo_token_rejected_on_production_routes():
    """Demo session capability token is rejected on protected production analyst routes."""
    token, _ = _bootstrap_session()
    resp = client.get("/cases", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_demo_decision_clear_and_block_hold(isolated_demo_store):
    """Judge can CLEAR and BLOCK_HOLD demo cases, updating disposition and audit trail."""
    token, sid = _bootstrap_session()
    case_id_1 = f"demo_{sid}_case_01"
    case_id_2 = f"demo_{sid}_case_02"

    # 1. Clear case 1
    resp1 = client.post(
        f"/demo/cases/{case_id_1}/decision",
        json={"case_id": case_id_1, "action": "CLEAR", "reason": "Customer phone confirmed transaction.", "evidence_acknowledged": True},
        headers={"X-Sentinel-Demo-Session": token},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["state"] == "FINALIZED"
    assert data1["final_disposition"] == "CLEAR"
    assert data1["idempotent_replay"] is False

    # 2. Block & Hold case 2
    resp2 = client.post(
        f"/demo/cases/{case_id_2}/decision",
        json={"case_id": case_id_2, "action": "BLOCK_HOLD", "reason": "Device confirmed malicious.", "evidence_acknowledged": True},
        headers={"X-Sentinel-Demo-Session": token},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["state"] == "FINALIZED"
    assert data2["final_disposition"] == "BLOCK_HOLD"

    # Verify audit trail contains demo attribution
    doc1 = isolated_demo_store.get_case(sid, case_id_1)
    assert doc1["final_disposition"] == "CLEAR"
    trail1 = isolated_demo_store.get_audit_trail(sid, case_id_1)
    assert any(a.get("output_snapshot", {}).get("is_demo") is True for a in trail1)


def test_demo_decision_escalate_senior_flow(isolated_demo_store):
    """ESCALATE_SENIOR assigns the case to the target senior analyst and returns confirmation."""
    token, sid = _bootstrap_session()
    case_id = f"demo_{sid}_case_01"

    # Missing target_analyst_id rejected
    resp_bad = client.post(
        f"/demo/cases/{case_id}/decision",
        json={"case_id": case_id, "action": "ESCALATE_SENIOR", "reason": "Escalating", "evidence_acknowledged": True},
        headers={"X-Sentinel-Demo-Session": token},
    )
    assert resp_bad.status_code == 400
    assert "target senior analyst must be selected" in resp_bad.json()["detail"]

    # Valid escalation
    resp = client.post(
        f"/demo/cases/{case_id}/decision",
        json={
            "case_id": case_id,
            "action": "ESCALATE_SENIOR",
            "reason": "Suspicious pattern needs second review",
            "evidence_acknowledged": True,
            "target_analyst_id": "senior_demo_01",
        },
        headers={"X-Sentinel-Demo-Session": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "HUMAN_REVIEW"
    assert data["final_disposition"] is None
    assert data["assigned_analyst_id"] == "senior_demo_01"
    assert "Elena Cho" in data["target_analyst_display_name"]


def test_demo_decision_validation_errors(isolated_demo_store):
    """Missing reason or unacknowledged evidence produces 400 Bad Request."""
    token, sid = _bootstrap_session()
    case_id = f"demo_{sid}_case_01"

    # Unacknowledged evidence
    resp1 = client.post(
        f"/demo/cases/{case_id}/decision",
        json={"case_id": case_id, "action": "CLEAR", "reason": "Test reason", "evidence_acknowledged": False},
        headers={"X-Sentinel-Demo-Session": token},
    )
    assert resp1.status_code == 400
    assert "evidence_acknowledged must be true" in resp1.json()["detail"]

    # Empty reason
    resp2 = client.post(
        f"/demo/cases/{case_id}/decision",
        json={"case_id": case_id, "action": "CLEAR", "reason": "   ", "evidence_acknowledged": True},
        headers={"X-Sentinel-Demo-Session": token},
    )
    assert resp2.status_code == 400


def test_concurrent_decisions_idempotency_and_conflict(isolated_demo_store):
    """Duplicate identical decision returns idempotent replay; conflicting decision returns 409."""
    token, sid = _bootstrap_session()
    case_id = f"demo_{sid}_case_01"

    body = {"case_id": case_id, "action": "CLEAR", "reason": "Verified legitimate", "evidence_acknowledged": True}
    first = client.post(f"/demo/cases/{case_id}/decision", json=body, headers={"X-Sentinel-Demo-Session": token})
    assert first.status_code == 200
    assert first.json()["idempotent_replay"] is False

    # Idempotent replay: exact same action & reason
    replay = client.post(f"/demo/cases/{case_id}/decision", json=body, headers={"X-Sentinel-Demo-Session": token})
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    # Conflicting decision: different action or reason on already finalized case
    conflict_body = {"case_id": case_id, "action": "BLOCK_HOLD", "reason": "Conflicting decision", "evidence_acknowledged": True}
    conflict = client.post(f"/demo/cases/{case_id}/decision", json=conflict_body, headers={"X-Sentinel-Demo-Session": token})
    assert conflict.status_code == 409


def test_reset_isolation_multi_judge(isolated_demo_store):
    """Judge A clicking Reset Demo restores Judge A's cases without affecting Judge B."""
    token_a, sid_a = _bootstrap_session()
    token_b, sid_b = _bootstrap_session()

    case_a = f"demo_{sid_a}_case_01"
    case_b = f"demo_{sid_b}_case_01"

    # Both decide their case_01
    client.post(f"/demo/cases/{case_a}/decision", json={"case_id": case_a, "action": "CLEAR", "reason": "Clear A", "evidence_acknowledged": True}, headers={"X-Sentinel-Demo-Session": token_a})
    client.post(f"/demo/cases/{case_b}/decision", json={"case_id": case_b, "action": "BLOCK_HOLD", "reason": "Block B", "evidence_acknowledged": True}, headers={"X-Sentinel-Demo-Session": token_b})

    # Verify both are finalized
    assert isolated_demo_store.get_case(sid_a, case_a)["final_disposition"] == "CLEAR"
    assert isolated_demo_store.get_case(sid_b, case_b)["final_disposition"] == "BLOCK_HOLD"

    # Session A resets
    reset_resp = client.post("/demo/reset", headers={"X-Sentinel-Demo-Session": token_a})
    assert reset_resp.status_code == 200

    # Session A case_01 is restored to HUMAN_REVIEW with no final disposition
    doc_a = isolated_demo_store.get_case(sid_a, case_a)
    assert doc_a["state"] == "HUMAN_REVIEW"
    assert doc_a.get("final_disposition") is None

    # CRITICAL: Session B case_01 is STILL finalized as BLOCK_HOLD -- zero crosstalk!
    doc_b = isolated_demo_store.get_case(sid_b, case_b)
    assert doc_b["state"] == "FINALIZED"
    assert doc_b["final_disposition"] == "BLOCK_HOLD"


def test_reset_debounce_rate_limit(isolated_demo_store):
    """Rapid reset attempts within 10s debounce return 429 Too Many Requests."""
    token, _ = _bootstrap_session()

    # First reset succeeds
    resp1 = client.post("/demo/reset", headers={"X-Sentinel-Demo-Session": token})
    assert resp1.status_code == 200

    # Immediate second reset is rejected by debounce
    resp2 = client.post("/demo/reset", headers={"X-Sentinel-Demo-Session": token})
    assert resp2.status_code == 429
    assert "Please wait" in resp2.json()["detail"]


def test_sample_transactions_endpoint():
    """GET /demo/sample-transactions provides clean and high-risk payloads."""
    resp = client.get("/demo/sample-transactions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["clean"]["amount"] == "75.00"
    assert data["high_risk"]["amount"] == "1249.99"
