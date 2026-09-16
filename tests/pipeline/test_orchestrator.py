"""Unit tests for the Phase 4.3 pipeline orchestrator, using an in-memory
fake CaseStore and scripted fake Gemini clients so orchestration mechanics
(clean-skip path, idempotency, state transitions, unknown transaction_id)
are tested deterministically and without a network dependency. The real,
fully-wired pipeline (real Firestore + real Gemini) is covered separately
by scripts/run_pipeline_scenarios.py and tests/pipeline/test_pipeline_live.py.
"""

from __future__ import annotations

import json

import pytest
from google.genai import types

from shared.contracts.case import CaseState
from shared.generator.seed_loader import load_scenario
from shared.pipeline.orchestrator import UnknownTransactionError, resolve_scenario_for_transaction, run_pipeline


class FakeCaseStore:
    """In-memory double implementing CaseStore's public surface."""

    def __init__(self) -> None:
        self.cases: dict[str, dict[str, object]] = {}
        self.transactions: dict[str, str] = {}
        self.audit_events: dict[str, list[dict[str, object]]] = {}

    def create_case_if_new(self, transaction_id: str, case_id: str, document: dict[str, object]):
        if transaction_id in self.transactions:
            return False, self.transactions[transaction_id]
        self.transactions[transaction_id] = case_id
        self.cases[case_id] = dict(document)
        self.audit_events[case_id] = []
        return True, case_id

    def get_case_id_for_transaction(self, transaction_id: str):
        return self.transactions.get(transaction_id)

    def update_case(self, case_id: str, updates: dict[str, object]) -> None:
        self.cases[case_id].update(updates)

    def get_case(self, case_id: str):
        return self.cases.get(case_id)

    def append_audit_event(self, case_id: str, audit_event) -> None:
        self.audit_events[case_id].append(audit_event.model_dump(mode="json"))


class _FakeAnalystRecord:
    def __init__(self, uid: str) -> None:
        self.uid = uid


class FakeAnalystDirectory:
    """In-memory double implementing AnalystDirectory's public surface used by
    the orchestrator's round-robin assignment."""

    def __init__(self, active_analyst_uids: list[str] | None = None) -> None:
        self._active_analyst_uids = active_analyst_uids if active_analyst_uids is not None else ["analyst_fake_1"]

    def list_active_analysts(self) -> list[_FakeAnalystRecord]:
        return [_FakeAnalystRecord(uid) for uid in self._active_analyst_uids]


class FakeAssignmentStore:
    """In-memory double implementing AssignmentStore's public surface: simple
    round-robin over whatever active_uids is passed each call."""

    def __init__(self) -> None:
        self._last_assigned: str | None = None

    def assign_next_analyst(self, active_uids: list[str]) -> str | None:
        if not active_uids:
            return None
        sorted_uids = sorted(set(active_uids))
        if self._last_assigned in sorted_uids:
            next_index = (sorted_uids.index(self._last_assigned) + 1) % len(sorted_uids)
        else:
            next_index = 0
        self._last_assigned = sorted_uids[next_index]
        return self._last_assigned


class FakeEvidenceGeminiClient:
    """Scripted fake Evidence Agent client: stops immediately with a plain-text turn,
    so the (already-mocked) fixture-required tools drive completeness."""

    model_name = "fake-gemini-flash"

    def generate_step(self, contents, system_instruction):  # noqa: D102 -- test double
        content = types.Content(
            role="model", parts=[types.Part.from_text(text="No further evidence needed.")]
        )
        return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], model_version=self.model_name)


class FakeReasoningGeminiClient:
    """Scripted fake Reasoning client returning a fixed, citation-valid payload."""

    model_name = "fake-gemini-pro"

    def __init__(self, risk_assessment: str = "MEDIUM") -> None:
        self._risk_assessment = risk_assessment

    def generate(self, system_instruction: str, user_content: str):  # noqa: D102 -- test double
        # Extract a real fact_id from the DATA block so the citation is valid.
        facts_marker = "--- EVIDENCE FACTS ---\n```json\n"
        start = user_content.index(facts_marker) + len(facts_marker)
        end = user_content.index("\n```", start)
        facts = json.loads(user_content[start:end])
        fact_ids = [f["fact_id"] for f in facts] or ["no_facts"]

        payload = {
            "risk_assessment": self._risk_assessment,
            "summary": "Test summary",
            "supporting_factors": (
                [{"statement": "test", "fact_ids": fact_ids[:1], "materiality": "MEDIUM"}] if fact_ids != ["no_facts"] else []
            ),
            "counter_factors": [],
            "evidence_gaps": [],
            "evidence_citations": (
                [{"claim_id": "claim_1", "fact_ids": fact_ids[:1]}] if fact_ids != ["no_facts"] else []
            ),
            "recommended_disposition": "CLEAR",
        }
        content = types.Content(role="model", parts=[types.Part.from_text(text=json.dumps(payload))])
        return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], model_version=self.model_name)


def test_unknown_transaction_id_raises() -> None:
    from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
    from datetime import datetime, timezone
    from decimal import Decimal

    unknown_tx = Transaction(
        transaction_id="tx_does_not_exist_anywhere",
        customer_id="cust_x",
        account_id="acc_x",
        card_id="card_x",
        merchant_id="merch_x",
        amount=Decimal("10.00"),
        currency="USD",
        timestamp=datetime(2026, 9, 15, tzinfo=timezone.utc),
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_x",
        ip_address="1.2.3.4",
        geo=Geo(lat=Decimal("0"), lon=Decimal("0"), country="USA"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )
    with pytest.raises(UnknownTransactionError):
        resolve_scenario_for_transaction(unknown_tx.transaction_id)
    with pytest.raises(UnknownTransactionError):
        run_pipeline(
            unknown_tx,
            case_store=FakeCaseStore(),
            analyst_directory=FakeAnalystDirectory(),
            assignment_store=FakeAssignmentStore(),
        )


def test_clean_normal_transaction_skips_investigation_and_auto_resolves() -> None:
    scenario = load_scenario("clean_normal")
    store = FakeCaseStore()

    result = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        analyst_directory=FakeAnalystDirectory(),
        assignment_store=FakeAssignmentStore(),
    )

    assert result["state"] == CaseState.AUTO_RESOLVED.value
    assert result["outcome"] is None  # Policy was never invoked
    assert result["rule_id"] is None
    assert result["duplicate"] is False

    case = store.get_case(result["case_id"])
    assert case["policy_decision"] is None
    assert case["evidence_bundle"] is None

    event_types = [e["event_type"] for e in store.audit_events[result["case_id"]]]
    assert "CASE_DETECTED" in event_types
    assert "CLEAN_TRANSACTION_AUTO_RESOLVED" in event_types
    # Never entered the investigation path.
    assert "CASE_FLAGGED" not in event_types


def test_duplicate_transaction_returns_existing_case_without_rerunning() -> None:
    scenario = load_scenario("clean_normal")
    store = FakeCaseStore()

    first = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        analyst_directory=FakeAnalystDirectory(),
        assignment_store=FakeAssignmentStore(),
    )
    second = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        analyst_directory=FakeAnalystDirectory(),
        assignment_store=FakeAssignmentStore(),
    )

    assert second["case_id"] == first["case_id"]
    assert second["duplicate"] is True
    # Only one case document was ever created.
    assert len(store.cases) == 1


def test_flagged_transaction_runs_full_pipeline_with_fake_clients() -> None:
    scenario = load_scenario("merchant_risk_trend")
    store = FakeCaseStore()

    result = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        evidence_client=FakeEvidenceGeminiClient(),
        reasoning_client=FakeReasoningGeminiClient(risk_assessment="MEDIUM"),
        analyst_directory=FakeAnalystDirectory(),
        assignment_store=FakeAssignmentStore(),
    )

    assert result["duplicate"] is False
    assert result["rule_id"] is not None
    assert result["outcome"] in {"AUTO_RESOLVE", "ESCALATE"}

    case = store.get_case(result["case_id"])
    assert case["evidence_bundle"] is not None
    assert case["findings"] is not None
    assert case["policy_decision"] is not None

    event_types = [e["event_type"] for e in store.audit_events[result["case_id"]]]
    assert event_types[:2] == ["CASE_DETECTED", "CASE_FLAGGED"]
    assert "POLICY_EVALUATED" in event_types
    assert event_types[-1] == result["state"]


def test_escalated_case_lands_in_human_review_not_a_resting_escalated_state() -> None:
    """Build Checklist Phase 5.1: POST /cases/{case_id}/decision requires the case to be
    in HUMAN_REVIEW, and GET /cases's queue view is exactly that set -- an escalated case
    must actually reach HUMAN_REVIEW, with ESCALATED recorded as its own audit moment
    immediately before it, not as the final resting state."""
    scenario = load_scenario("merchant_risk_trend")
    store = FakeCaseStore()

    result = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        evidence_client=FakeEvidenceGeminiClient(),
        reasoning_client=FakeReasoningGeminiClient(risk_assessment="MEDIUM"),
        analyst_directory=FakeAnalystDirectory(["analyst_fake_1"]),
        assignment_store=FakeAssignmentStore(),
    )

    assert result["outcome"] == "ESCALATE"
    assert result["state"] == CaseState.HUMAN_REVIEW.value
    case = store.get_case(result["case_id"])
    assert case["state"] == CaseState.HUMAN_REVIEW.value
    # Deterministic round-robin assignment fires on first HUMAN_REVIEW entry
    # (V1 Authoritative Ruling Part 4/5).
    assert case["assigned_analyst_id"] == "analyst_fake_1"

    event_types = [e["event_type"] for e in store.audit_events[result["case_id"]]]
    assert event_types[-2:] == ["ESCALATED", "HUMAN_REVIEW"]


def test_flagged_transaction_with_reasoning_failure_never_auto_resolves() -> None:
    class AlwaysMalformedReasoningClient:
        model_name = "fake-gemini-pro-broken"

        def generate(self, system_instruction: str, user_content: str):
            content = types.Content(role="model", parts=[types.Part.from_text(text="not json")])
            return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], model_version=self.model_name)

    scenario = load_scenario("merchant_risk_trend")
    store = FakeCaseStore()

    result = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        evidence_client=FakeEvidenceGeminiClient(),
        reasoning_client=AlwaysMalformedReasoningClient(),
        analyst_directory=FakeAnalystDirectory(),
        assignment_store=FakeAssignmentStore(),
    )

    assert result["outcome"] == "ESCALATE"
    assert result["state"] == CaseState.HUMAN_REVIEW.value
    case = store.get_case(result["case_id"])
    assert case["findings"] is None
    assert case["robustness"] is None  # never scored -- no findings to score
