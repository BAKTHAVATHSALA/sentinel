"""Unit tests for the Phase 4.3 pipeline orchestrator, using an in-memory
fake CaseStore and scripted fake Gemini clients so orchestration mechanics
(clean-skip path, idempotency, state transitions, unknown transaction_id)
are tested deterministically and without a network dependency. The real,
fully-wired pipeline (real Firestore + real Gemini) is covered separately
by scripts/run_pipeline_scenarios.py and tests/pipeline/test_pipeline_live.py.
"""

from __future__ import annotations

import json

from google.genai import types

from shared.contracts.case import CaseState
from shared.generator.seed_loader import load_scenario
from shared.pipeline.orchestrator import resolve_scenario_for_transaction, run_pipeline


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
    def __init__(self, uid: str, role: str = "ANALYST") -> None:
        self.uid = uid
        self.display_name = f"Fake Analyst {uid}"
        self.email = f"{uid}@sentinel.demo"
        self.role = role


class FakeAnalystDirectory:
    """In-memory double implementing AnalystDirectory's public surface used by
    the orchestrator's round-robin assignment. `other_records` lets a test
    seed non-active-ANALYST records (e.g. a SENIOR_ANALYST an escalation
    reassigned a case to) that `.get()` can still resolve by uid, the same
    way the real Firestore-backed directory would."""

    def __init__(
        self,
        active_analyst_uids: list[str] | None = None,
        other_records: list[_FakeAnalystRecord] | None = None,
    ) -> None:
        self._active_analyst_uids = active_analyst_uids if active_analyst_uids is not None else ["analyst_fake_1"]
        self._other_records = {r.uid: r for r in (other_records or [])}

    def list_active_analysts(self) -> list[_FakeAnalystRecord]:
        return [_FakeAnalystRecord(uid) for uid in self._active_analyst_uids]

    def get(self, uid: str) -> _FakeAnalystRecord | None:
        if uid in self._active_analyst_uids:
            return _FakeAnalystRecord(uid)
        return self._other_records.get(uid)


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


def _make_unknown_transaction(transaction_id: str = "tx_does_not_exist_anywhere") -> "Transaction":
    from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
    from datetime import datetime, timezone
    from decimal import Decimal

    return Transaction(
        transaction_id=transaction_id,
        customer_id="cust_unknown_x",
        account_id="acc_unknown_x",
        card_id="card_unknown_x",
        merchant_id="merch_unknown_x",
        amount=Decimal("899.99"),
        currency="USD",
        timestamp=datetime(2026, 9, 18, 14, 0, 0, tzinfo=timezone.utc),
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_unknown_x",
        ip_address="198.51.100.50",
        geo=Geo(lat=Decimal("25.7617"), lon=Decimal("-80.1918"), country="USA"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )


def test_unknown_transaction_id_resolves_a_synthetic_context_instead_of_being_rejected() -> None:
    """build.md: unknown transaction != automatic fraud, and != rejection --
    a transaction_id matching no committed fixture now falls through to
    deterministic synthesis (shared/generator/synthesis.py) and runs the
    REAL, unmodified pipeline instead of raising."""
    unknown_tx = _make_unknown_transaction()
    scenario = resolve_scenario_for_transaction(unknown_tx)
    assert scenario.metadata.get("synthetic") is True
    assert scenario.target_transaction == unknown_tx

    result = run_pipeline(
        unknown_tx,
        case_store=FakeCaseStore(),
        evidence_client=FakeEvidenceGeminiClient(),
        reasoning_client=FakeReasoningGeminiClient(risk_assessment="LOW"),
        analyst_directory=FakeAnalystDirectory(),
        assignment_store=FakeAssignmentStore(),
    )
    # The result is whatever the real pipeline determined -- not asserted to
    # be any particular outcome, only that it completed (Policy always
    # produces AUTO_RESOLVE or ESCALATE, never anything else).
    assert result["outcome"] in {None, "AUTO_RESOLVE", "ESCALATE"}
    assert result["duplicate"] is False


def test_known_seeded_scenarios_are_matched_before_falling_back_to_synthesis() -> None:
    """Existing committed fixtures must remain completely unaffected by the
    synthesis fallback -- a known transaction_id still resolves the exact
    committed scenario, never a synthesized substitute."""
    known_scenario = load_scenario("clean_normal")
    resolved = resolve_scenario_for_transaction(known_scenario.target_transaction)

    assert resolved.scenario_name == known_scenario.scenario_name
    assert resolved.customer_profile == known_scenario.customer_profile
    assert resolved.metadata.get("synthetic") is not True


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
    assert result["assignment"] is None  # AUTO_RESOLVE never has an assignment

    # Public decision summary: real detection facts, no policy ever ran.
    summary = result["decision_summary"]
    assert set(summary.keys()) == {
        "risk_assessment",
        "anomaly_tags",
        "policy_rule_id",
        "reasons",
        "evidence_completeness",
        "merchant_flagged",
    }
    assert summary["risk_assessment"] == "LOW"
    assert summary["anomaly_tags"] == []
    assert summary["policy_rule_id"] is None
    assert summary["reasons"] == []
    assert summary["evidence_completeness"] is None
    assert summary["merchant_flagged"] is False

    case = store.get_case(result["case_id"])
    assert case["policy_decision"] is None
    assert case["evidence_bundle"] is None

    event_types = [e["event_type"] for e in store.audit_events[result["case_id"]]]
    assert "CASE_DETECTED" in event_types
    assert "CLEAN_TRANSACTION_AUTO_RESOLVED" in event_types
    # Never entered the investigation path.
    assert "CASE_FLAGGED" not in event_types


def test_clean_transaction_with_elevated_risk_band_reaches_human_review_without_investigation() -> None:
    """CLEAN (zero anomaly tags) is necessary but not sufficient for
    AUTO_RESOLVE -- Rule P-004 (Contracts S16) has always also required
    risk_score <= LOW. This identity/amount combination is verified
    deterministic (shared.detection.detect_transaction called directly on
    this exact input reproducibly yields risk_band=HIGH, risk_score=0.77,
    anomaly_tags=[] -- the amount ($650) stays well under this identity's
    UNUSUAL_AMOUNT sigma cutoff of $996, so no anomaly tag fires, while the
    continuous risk model still scores it HIGH). CLEAN but not LOW-risk must
    still reach HUMAN_REVIEW, never AUTO_RESOLVED, and must still skip
    Evidence/Reasoning/Robustness/Policy entirely since there is no anomaly
    tag to investigate."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
    from shared.generator.synthesis import derive_customer_baseline

    customer_id, account_id, card_id = "cust_p004_live_v13", "acc_p004_live_v13", "card_p004_live_v13"
    customer, known_devices = derive_customer_baseline(customer_id, account_id, card_id)

    tx = Transaction(
        transaction_id="tx_clean_elevated_risk_test",
        customer_id=customer_id,
        account_id=account_id,
        card_id=card_id,
        merchant_id="merch_p004_live_v13",
        amount=Decimal("650.00"),  # elevates risk_score without crossing the anomaly-tag threshold
        currency="USD",
        timestamp=datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc),
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id=known_devices[0],
        ip_address=customer.primary_ip,
        geo=Geo(lat=customer.home_geo.lat, lon=customer.home_geo.lon, country=customer.home_geo.country),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )
    store = FakeCaseStore()

    result = run_pipeline(
        tx,
        case_store=store,
        analyst_directory=FakeAnalystDirectory(["analyst_fake_1"]),
        assignment_store=FakeAssignmentStore(),
    )

    summary = result["decision_summary"]
    assert summary["anomaly_tags"] == []  # CLEAN
    assert summary["risk_assessment"] == "HIGH"  # elevated, not LOW -- the case this test targets
    assert result["state"] == CaseState.HUMAN_REVIEW.value
    assert result["outcome"] is None  # Policy was never invoked -- nothing to investigate
    assert result["rule_id"] is None
    assert result["assignment"] == {"analyst_name": "Fake Analyst analyst_fake_1"}

    case = store.get_case(result["case_id"])
    assert case["evidence_bundle"] is None
    assert case["findings"] is None
    assert case["policy_decision"] is None
    assert case["state"] == CaseState.HUMAN_REVIEW.value

    event_types = [e["event_type"] for e in store.audit_events[result["case_id"]]]
    assert "CASE_FLAGGED" not in event_types  # never entered the investigation path
    assert event_types[-2:] == ["ESCALATED", "HUMAN_REVIEW"]


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
    # The duplicate path's decision_summary is read from the same persisted
    # document, not recomputed -- must match the original exactly.
    assert second["decision_summary"] == first["decision_summary"]


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
    # Transaction Console assignment field: display name only -- no email,
    # no UID, no role.
    assert result["assignment"] == {"analyst_name": "Fake Analyst analyst_fake_1"}
    assert set(result["assignment"].keys()) == {"analyst_name"}

    # Public decision summary: real facts from this exact investigation --
    # MERCHANT_RISK is the scenario's designed single signal, so
    # merchant_flagged must be True and the anomaly tag list must include it.
    summary = result["decision_summary"]
    assert set(summary.keys()) == {
        "risk_assessment",
        "anomaly_tags",
        "policy_rule_id",
        "reasons",
        "evidence_completeness",
        "merchant_flagged",
    }
    assert summary["risk_assessment"] == "MEDIUM"  # from FakeReasoningGeminiClient(risk_assessment="MEDIUM")
    assert "MERCHANT_RISK" in summary["anomaly_tags"]
    assert summary["merchant_flagged"] is True
    assert summary["policy_rule_id"] == result["rule_id"]
    assert summary["reasons"] == case["policy_decision"]["reasons"]
    assert summary["evidence_completeness"] == case["evidence_bundle"]["completeness"]
    # No protected case content leaks into the public summary.
    assert "summary" not in summary  # no raw Gemini findings text
    assert "tools_called" not in summary
    assert "facts" not in summary

    event_types = [e["event_type"] for e in store.audit_events[result["case_id"]]]
    assert event_types[-2:] == ["ESCALATED", "HUMAN_REVIEW"]


def test_zero_active_analysts_leaves_assignment_null() -> None:
    """Addendum 1 Point 2: a HUMAN_REVIEW case with no active analyst pool
    stays unassigned -- the Transaction Console's assignment field must be
    null, not a fabricated analyst."""
    scenario = load_scenario("merchant_risk_trend")
    store = FakeCaseStore()

    result = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        evidence_client=FakeEvidenceGeminiClient(),
        reasoning_client=FakeReasoningGeminiClient(risk_assessment="MEDIUM"),
        analyst_directory=FakeAnalystDirectory([]),
        assignment_store=FakeAssignmentStore(),
    )

    assert result["state"] == CaseState.HUMAN_REVIEW.value
    case = store.get_case(result["case_id"])
    assert case["assigned_analyst_id"] is None
    assert result["assignment"] is None


def test_duplicate_human_review_transaction_returns_existing_assignment() -> None:
    """A duplicate POST /transactions for an already-escalated case must report
    the same assignment the first call produced -- not re-run assignment, and
    not silently drop it (V1 Authoritative Ruling Part 4/5, Safety Invariant 9)."""
    scenario = load_scenario("merchant_risk_trend")
    store = FakeCaseStore()
    directory = FakeAnalystDirectory(["analyst_fake_1"])

    first = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        evidence_client=FakeEvidenceGeminiClient(),
        reasoning_client=FakeReasoningGeminiClient(risk_assessment="MEDIUM"),
        analyst_directory=directory,
        assignment_store=FakeAssignmentStore(),
    )
    assert first["state"] == CaseState.HUMAN_REVIEW.value

    second = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        analyst_directory=directory,
        assignment_store=FakeAssignmentStore(),
    )

    assert second["duplicate"] is True
    assert second["assignment"] == first["assignment"]
    assert second["assignment"] == {"analyst_name": "Fake Analyst analyst_fake_1"}


def test_duplicate_case_reassigned_to_senior_never_exposes_senior_identity() -> None:
    """A case previously ESCALATE_SENIOR-reassigned (services/api/cases.py,
    unrelated to and unchanged by this pipeline) now has a SENIOR_ANALYST as
    its assigned_analyst_id. A duplicate POST /transactions for that same
    transaction_id must not leak that senior's identity through the public
    Transaction Console's assignment field -- only the normal round-robin
    ANALYST pool is ever surfaced there."""
    scenario = load_scenario("merchant_risk_trend")
    store = FakeCaseStore()
    transaction_id = scenario.target_transaction.transaction_id
    store.transactions[transaction_id] = "case_reassigned_to_senior"
    store.cases["case_reassigned_to_senior"] = {
        "case_id": "case_reassigned_to_senior",
        "state": CaseState.HUMAN_REVIEW.value,
        "assigned_analyst_id": "senior_fake_1",
        "policy_decision": {"outcome": "ESCALATE", "rule_id": "P-002"},
    }
    directory = FakeAnalystDirectory(
        ["analyst_fake_1"], other_records=[_FakeAnalystRecord("senior_fake_1", role="SENIOR_ANALYST")]
    )

    result = run_pipeline(
        scenario.target_transaction,
        case_store=store,
        analyst_directory=directory,
        assignment_store=FakeAssignmentStore(),
    )

    assert result["duplicate"] is True
    assert result["assignment"] is None


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
