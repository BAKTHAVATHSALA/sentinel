"""Unit tests for the Phase 2.1 evidence tool layer against committed seed fixtures."""

from __future__ import annotations

import time

import pytest

from shared.contracts.fact import Fact, FactQuality
from shared.evidence.errors import ToolTimeoutError, ToolValidationError, UnknownToolError
from shared.evidence.fixtures import build_fixture_context
from shared.evidence.tools import TOOL_TIMEOUT_SECONDS, call_tool
from shared.generator.seed_loader import load_scenario


def _ctx(stem: str, case_id: str = "case_test"):
    return build_fixture_context(load_scenario(stem), case_id=case_id)


def test_call_tool_rejects_unknown_tool_name() -> None:
    """1. Verify a tool name outside the six-tool allow-list is rejected, never executed."""
    ctx = _ctx("clean_normal")
    with pytest.raises(UnknownToolError):
        call_tool("get_transaction_history", {"customer_id": ctx.customer.customer_id}, ctx, 1)


def test_call_tool_rejects_invalid_input_schema() -> None:
    """2. Verify missing required arguments raise a structured ToolValidationError."""
    ctx = _ctx("clean_normal")
    with pytest.raises(ToolValidationError):
        call_tool("get_device_history", {"customer_id": ctx.customer.customer_id}, ctx, 1)


def test_call_tool_rejects_unknown_customer_reference() -> None:
    """3. Verify a customer_id outside this case's known entities is rejected, not silently
    answered against the wrong customer."""
    ctx = _ctx("clean_normal")
    with pytest.raises(ToolValidationError):
        call_tool(
            "get_device_history",
            {"customer_id": "cust_does_not_exist", "device_id": ctx.transaction.device_id},
            ctx,
            1,
        )


def test_get_device_history_known_device_for_clean_scenario() -> None:
    """4. Verify a customer's own primary device resolves as known with no risk signals."""
    ctx = _ctx("clean_normal")
    fact = call_tool(
        "get_device_history",
        {"customer_id": ctx.customer.customer_id, "device_id": ctx.customer.primary_device_id},
        ctx,
        1,
    )
    assert isinstance(fact, Fact)
    assert fact.source_tool == "get_device_history"
    assert fact.value["known_device"] is True
    assert fact.value["device_risk_signals"] == []
    assert fact.quality == FactQuality.VERIFIED


def test_get_device_history_new_device_reveals_cross_account_signal_in_branching_proof() -> None:
    """5. Verify the branching-proof fixture's explicit device_history_fixture is served
    verbatim: new device, seen on a different account 2 hours prior."""
    ctx = _ctx("branching_proof")
    fact = call_tool(
        "get_device_history",
        {"customer_id": ctx.customer.customer_id, "device_id": ctx.transaction.device_id},
        ctx,
        1,
    )
    assert fact.value["known_device"] is False
    signal = fact.value["device_risk_signals"][0]
    assert signal["signal"] == "SEEN_ON_DIFFERENT_ACCOUNT"
    assert signal["other_account_id"] == "acc_5741"
    assert signal["hours_before_target"] == 2
    assert fact.quality == FactQuality.VERIFIED


def test_get_linked_entities_follows_the_branching_proof_device_link() -> None:
    """6. Verify following up on the revealed account surfaces the linked customer and
    the seeded recent anomaly -- the payload that makes the branch worth taking."""
    ctx = _ctx("branching_proof")
    fact = call_tool(
        "get_linked_entities",
        {"customer_id": ctx.customer.customer_id, "account_id": "acc_5741"},
        ctx,
        2,
    )
    assert "cust_sc_branch_secondary" in fact.value["linked_customers"]
    assert len(fact.value["recent_anomalies"]) >= 1
    assert fact.source_tool == "get_linked_entities"
    assert fact.subject_id == "acc_5741"


def test_get_linked_entities_rejects_unknown_account() -> None:
    """7. Verify asking about an account never mentioned in this case's fixtures fails loudly."""
    ctx = _ctx("branching_proof")
    with pytest.raises(ToolValidationError):
        call_tool(
            "get_linked_entities",
            {"customer_id": ctx.customer.customer_id, "account_id": "acc_never_seen"},
            ctx,
            2,
        )


def test_get_merchant_risk_matches_merchant_profile() -> None:
    """8. Verify get_merchant_risk reflects the seeded merchant-risk-trend fixture's
    rising trend and zero prior transactions with a genuinely new-to-customer merchant."""
    ctx = _ctx("merchant_risk_trend")
    fact = call_tool(
        "get_merchant_risk",
        {"merchant_id": ctx.merchant.merchant_id, "customer_id": ctx.customer.customer_id},
        ctx,
        1,
    )
    assert fact.value["fraud_report_trend"] == "RISING"
    assert fact.value["customer_prior_transactions_with_merchant"] == 0
    assert fact.value["risk_band"] == "HIGH"


def test_get_merchant_risk_rejects_unknown_merchant() -> None:
    """9. Verify a merchant_id outside this case is rejected."""
    ctx = _ctx("merchant_risk_trend")
    with pytest.raises(ToolValidationError):
        call_tool(
            "get_merchant_risk",
            {"merchant_id": "merch_not_in_case", "customer_id": ctx.customer.customer_id},
            ctx,
            1,
        )


def test_get_ip_geovelocity_computes_distance_and_elapsed_time() -> None:
    """10. Verify get_ip_geovelocity computes a real haversine distance against the
    customer's most recent prior transaction location."""
    ctx = _ctx("signature_fraud")
    tx = ctx.transaction
    fact = call_tool(
        "get_ip_geovelocity",
        {
            "customer_id": ctx.customer.customer_id,
            "current_ip": tx.ip_address,
            "current_geo": {"lat": str(tx.geo.lat), "lon": str(tx.geo.lon), "country": tx.geo.country},
            "transaction_timestamp": tx.timestamp.isoformat(),
        },
        ctx,
        1,
    )
    assert float(fact.value["distance_km"]) >= 0
    assert float(fact.value["elapsed_hours"]) > 0
    assert fact.source_tool == "get_ip_geovelocity"


def test_get_behavioral_baseline_hydrates_transaction_id_reference() -> None:
    """11. Verify the lightweight {customer_id, transaction_id} Gemini-facing schema
    correctly hydrates into the full BehavioralBaselineInput.transaction contract field."""
    ctx = _ctx("clean_normal")
    fact = call_tool(
        "get_behavioral_baseline",
        {"customer_id": ctx.customer.customer_id, "transaction_id": ctx.transaction.transaction_id},
        ctx,
        1,
    )
    assert fact.value["historical_transaction_count"] == len(ctx.baseline_transactions)


def test_get_behavioral_baseline_rejects_mismatched_transaction_id() -> None:
    """12. Verify a transaction_id that doesn't belong to this case's transaction is rejected."""
    ctx = _ctx("clean_normal")
    with pytest.raises(ToolValidationError):
        call_tool(
            "get_behavioral_baseline",
            {"customer_id": ctx.customer.customer_id, "transaction_id": "tx_someone_elses"},
            ctx,
            1,
        )


def test_get_mock_kyc_status_reflects_customer_profile() -> None:
    """13. Verify get_mock_kyc_status reflects the customer's seeded KYC status."""
    ctx = _ctx("branching_proof")
    fact = call_tool("get_mock_kyc_status", {"customer_id": ctx.customer.customer_id}, ctx, 1)
    assert fact.value["kyc_status"] == "VERIFIED"
    assert fact.value["kyc_flags"] == []


def test_forced_tool_failure_raises_timeout_within_bounded_budget() -> None:
    """14. Verify the partial-evidence scenario's deliberately-forced get_device_history
    failure genuinely exhausts the per-tool timeout budget rather than being faked."""
    ctx = _ctx("partial_evidence")
    started = time.monotonic()
    with pytest.raises(ToolTimeoutError):
        call_tool(
            "get_device_history",
            {"customer_id": ctx.customer.customer_id, "device_id": ctx.transaction.device_id},
            ctx,
            1,
        )
    elapsed = time.monotonic() - started
    assert elapsed >= TOOL_TIMEOUT_SECONDS
    assert elapsed < TOOL_TIMEOUT_SECONDS + 2.0


def test_fact_ids_are_unique_and_ordered_by_call_index() -> None:
    """15. Verify fact_id encodes case_id and call sequence, so facts across a multi-call
    investigation are distinguishable and orderable."""
    ctx = _ctx("clean_normal")
    fact1 = call_tool(
        "get_device_history",
        {"customer_id": ctx.customer.customer_id, "device_id": ctx.customer.primary_device_id},
        ctx,
        1,
    )
    fact2 = call_tool("get_mock_kyc_status", {"customer_id": ctx.customer.customer_id}, ctx, 2)
    assert fact1.fact_id != fact2.fact_id
    assert fact1.fact_id.endswith("_01_get_device_history")
    assert fact2.fact_id.endswith("_02_get_mock_kyc_status")
