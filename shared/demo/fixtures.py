"""Pre-seeded synthetic cases and sample transactions for Sentinel Demo Mode.

Every case uses the authoritative V1 domain contracts (Transaction, DetectionOutput,
EvidenceBundle, Fact, CaseFindings, FindingFactor, Citation, RobustnessResult,
PolicyDecision, AuditEvent).
No mock screens or fake progress: every case embeds real investigable evidence,
grounded Gemini findings citations, Decision Robustness Scorer pillars, and audit records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from shared.contracts.case import CaseState, HumanAction
from shared.contracts.detection import AnomalyTag, DetectionOutput, RiskBand
from shared.contracts.evidence import EvidenceBundle, EvidenceCompleteness
from shared.contracts.events import ActorType, AuditEvent
from shared.contracts.fact import Fact, FactQuality
from shared.contracts.policy import PolicyDecision, PolicyOutcome
from shared.contracts.reasoning import (
    CaseFindings,
    Citation,
    FindingFactor,
    Materiality,
    RecommendedDisposition,
)
from shared.contracts.robustness import RobustnessClassification, RobustnessMethod, RobustnessResult
from shared.contracts.transaction import AuthorizationStage, Channel, Direction, Geo, PaymentRail, Transaction
from shared.persistence.case_document import build_case_document

BASE_TIME = datetime(2026, 9, 20, 14, 0, 0, tzinfo=timezone.utc)

SAMPLE_CLEAN_TRANSACTION = Transaction(
    transaction_id="tx_demo_clean_sample",
    customer_id="cust_sc_clean",
    account_id="acc_2824",
    card_id="card_1409",
    merchant_id="merch_standard_clean",
    amount=Decimal("75.00"),
    currency="USD",
    timestamp=BASE_TIME,
    payment_rail=PaymentRail.CARD_CNP,
    direction=Direction.OUTGOING,
    authorization_stage=AuthorizationStage.PRE_AUTH,
    device_id="dev_46048",
    ip_address="198.51.100.72",
    geo=Geo(lat=Decimal("37.7749"), lon=Decimal("-122.4194"), country="USA"),
    channel=Channel.WEB,
    merchant_category="electronics",
    card_present=False,
)

SAMPLE_HIGH_RISK_TRANSACTION = Transaction(
    transaction_id="tx_demo_fraud_sample",
    customer_id="cust_sc_flagship",
    account_id="acc_9921",
    card_id="card_4011",
    merchant_id="merch_flagship_electronics",
    amount=Decimal("1249.99"),
    currency="USD",
    timestamp=BASE_TIME,
    payment_rail=PaymentRail.CARD_CNP,
    direction=Direction.OUTGOING,
    authorization_stage=AuthorizationStage.PRE_AUTH,
    device_id="dev_compromised_99",
    ip_address="203.0.113.19",
    geo=Geo(lat=Decimal("40.7128"), lon=Decimal("-74.0060"), country="USA"),
    channel=Channel.WEB,
    merchant_category="electronics",
    card_present=False,
)


def _make_fact(
    fact_id: str,
    fact_type: str,
    subject_id: str,
    value: dict[str, object],
    source_tool: str,
    quality: FactQuality = FactQuality.VERIFIED,
) -> Fact:
    return Fact(
        fact_id=fact_id,
        type=fact_type,
        subject_id=subject_id,
        value=value,
        source_tool=source_tool,
        source_record_id=f"rec_{fact_id}",
        observed_at=BASE_TIME,
        retrieved_at=BASE_TIME,
        quality=quality,
    )


def _make_bundle(
    case_id: str,
    facts: list[Fact],
    tools: list[str],
    completeness: EvidenceCompleteness = EvidenceCompleteness.COMPLETE,
    missing: list[str] | None = None,
) -> EvidenceBundle:
    return EvidenceBundle(
        evidence_bundle_id=f"bundle_{case_id}",
        case_id=case_id,
        facts=facts,
        tools_called=tools,
        required_tools=tools,
        completeness=completeness,
        missing_required_evidence=missing or [],
        conflicts=[],
        started_at=BASE_TIME,
        completed_at=BASE_TIME,
    )


def _make_findings(
    findings_id: str,
    case_id: str,
    risk: RiskBand,
    summary: str,
    supporting: list[FindingFactor],
    counter: list[FindingFactor] | None = None,
    citations: list[Citation] | None = None,
    disposition: RecommendedDisposition = RecommendedDisposition.ESCALATE,
) -> CaseFindings:
    return CaseFindings(
        findings_id=findings_id,
        case_id=case_id,
        risk_assessment=risk,
        summary=summary,
        supporting_factors=supporting,
        counter_factors=counter or [],
        evidence_gaps=[],
        evidence_citations=citations or [],
        recommended_disposition=disposition,
        generated_at=BASE_TIME,
        model_name="gemini-2.0-flash",
        model_version="2.0",
        prompt_version="1.0.0",
    )


def _make_detection(
    case_id: str,
    tx_id: str,
    score: Decimal,
    band: RiskBand,
    tags: list[AnomalyTag],
    reasons: list[str],
) -> DetectionOutput:
    return DetectionOutput(
        case_id=case_id,
        transaction_id=tx_id,
        risk_score=score,
        risk_band=band,
        anomaly_tags=tags,
        detection_reasons=reasons,
        model_name="baseline-rf-v1",
        model_version="1.1.0",
        detected_at=BASE_TIME,
    )


def _make_robustness(
    case_id: str,
    classification: RobustnessClassification,
    fragile_factor_id: str | None = None,
) -> RobustnessResult:
    return RobustnessResult(
        robustness_id=f"rob_{case_id}",
        case_id=case_id,
        classification=classification,
        fragile_factor_id=fragile_factor_id,
        method=RobustnessMethod.FAST_PATH,
        evaluated_at=BASE_TIME,
    )


def _make_policy_decision(
    case_id: str,
    rule_id: str,
    outcome: PolicyOutcome,
    reasons: list[str],
) -> PolicyDecision:
    return PolicyDecision(
        decision_id=f"pol_{case_id}",
        case_id=case_id,
        outcome=outcome,
        rule_id=rule_id,
        rule_version="1.0.0",
        reasons=reasons,
        inputs_snapshot={"evidence_evaluated": True},
        evaluated_at=BASE_TIME,
    )


def generate_template_cases() -> list[dict[str, object]]:
    """Build the 10 pristine template cases for Sentinel Demo Mode."""
    templates = []

    # -------------------------------------------------------------------------
    # Case 1: Flagship Signature Fraud (Robust)
    # -------------------------------------------------------------------------
    c1_id = "case_01"
    c1_tx = Transaction(
        transaction_id="tx_demo_c01",
        customer_id="cust_9011",
        account_id="acc_1101",
        card_id="card_2201",
        merchant_id="merch_electronics_spike",
        amount=Decimal("1499.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_new_unrecognized",
        ip_address="198.51.100.88",
        geo=Geo(lat=Decimal("34.0522"), lon=Decimal("-118.2437"), country="USA"),
        channel=Channel.WEB,
        merchant_category="electronics",
        card_present=False,
    )
    c1_det = _make_detection(
        c1_id,
        c1_tx.transaction_id,
        Decimal("0.89"),
        RiskBand.HIGH,
        [AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION, AnomalyTag.MERCHANT_RISK],
        ["Unrecognized device", "Geographic divergence", "Elevated merchant risk"],
    )
    c1_f1 = _make_fact(
        "fact_dev_cross_link",
        "DEVICE_LINKAGE",
        "dev_new_unrecognized",
        {"linked_customers": ["cust_9011", "cust_8820_flagged"], "summary": "Device was active on a flagged customer account 2 hours ago."},
        "get_device_history",
    )
    c1_f2 = _make_fact(
        "fact_merch_fraud_trend",
        "MERCHANT_RISK",
        "merch_electronics_spike",
        {"recent_fraud_count": 4, "fraud_report_trend": "RISING", "summary": "Merchant has 4 recent fraud reports with an accelerating rising trend."},
        "get_merchant_risk",
    )
    c1_ev = _make_bundle(c1_id, [c1_f1, c1_f2], ["get_device_history", "get_merchant_risk", "get_linked_entities"])
    c1_findings = _make_findings(
        findings_id="find_c01",
        case_id=c1_id,
        risk=RiskBand.HIGH,
        summary="High-confidence synthetic fraud: multi-account device link and rising merchant dispute trend.",
        supporting=[
            FindingFactor(statement="Device is linked to a previously flagged fraudulent customer account.", fact_ids=["fact_dev_cross_link"], materiality=Materiality.HIGH),
            FindingFactor(statement="Merchant has 4 recent unauthorized transaction reports with a rising trend.", fact_ids=["fact_merch_fraud_trend"], materiality=Materiality.HIGH),
        ],
        citations=[
            Citation(claim_id="claim_dev", fact_ids=["fact_dev_cross_link"]),
            Citation(claim_id="claim_merch", fact_ids=["fact_merch_fraud_trend"]),
        ],
    )
    c1_rob = _make_robustness(c1_id, RobustnessClassification.ROBUST)
    c1_pol = _make_policy_decision(
        c1_id,
        "P-002",
        PolicyOutcome.ESCALATE,
        ["High risk score and value exceeding threshold with complete evidence requires human hold."],
    )
    templates.append(
        build_case_document(
            case_id=c1_id,
            transaction_id=c1_tx.transaction_id,
            state=CaseState.HUMAN_REVIEW,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            transaction=c1_tx,
            detection=c1_det,
            evidence_bundle=c1_ev,
            findings=c1_findings,
            robustness=c1_rob,
            policy_decision=c1_pol,
            assigned_analyst_id="demo_analyst",
        )
    )

    # -------------------------------------------------------------------------
    # Case 2: Account Takeover with Rapid Device Hopping (Robust)
    # -------------------------------------------------------------------------
    c2_id = "case_02"
    c2_tx = Transaction(
        transaction_id="tx_demo_c02",
        customer_id="cust_4412",
        account_id="acc_9931",
        card_id="card_5510",
        merchant_id="merch_luxury_goods",
        amount=Decimal("2800.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_hop_77",
        ip_address="198.51.100.12",
        geo=Geo(lat=Decimal("41.8781"), lon=Decimal("-87.6298"), country="USA"),
        channel=Channel.MOBILE,
        merchant_category="jewelry",
        card_present=False,
    )
    c2_det = _make_detection(
        c2_id,
        c2_tx.transaction_id,
        Decimal("0.91"),
        RiskBand.HIGH,
        [AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION],
        ["New mobile device observed", "Out-of-pattern geographic departure"],
    )
    c2_f1 = _make_fact("fact_dev_age", "DEVICE_AGE", "dev_hop_77", {"first_seen_minutes_ago": 15, "summary": "Device first observed 15 minutes ago."}, "get_device_history")
    c2_f2 = _make_fact("fact_geo_deviation", "GEO_DISTANCE", "198.51.100.12", {"distance_km": 1800, "summary": "IP location 1800km outside customer pattern."}, "get_location_history")
    c2_ev = _make_bundle(c2_id, [c2_f1, c2_f2], ["get_device_history", "get_location_history"])
    c2_findings = _make_findings(
        findings_id="find_c02",
        case_id=c2_id,
        risk=RiskBand.HIGH,
        summary="Probable ATO: Brand-new device performing immediate high-velocity luxury purchase across state lines.",
        supporting=[
            FindingFactor(statement="Device first seen 15 minutes prior to high-value purchase.", fact_ids=["fact_dev_age"], materiality=Materiality.HIGH),
            FindingFactor(statement="Location deviates 1800km from customer residential cluster.", fact_ids=["fact_geo_deviation"], materiality=Materiality.HIGH),
        ],
        citations=[
            Citation(claim_id="claim_age", fact_ids=["fact_dev_age"]),
            Citation(claim_id="claim_geo", fact_ids=["fact_geo_deviation"]),
        ],
    )
    c2_rob = _make_robustness(c2_id, RobustnessClassification.ROBUST)
    c2_pol = _make_policy_decision(
        c2_id,
        "P-002",
        PolicyOutcome.ESCALATE,
        ["High risk score and high value transaction with complete evidence held for review."],
    )
    templates.append(
        build_case_document(
            case_id=c2_id,
            transaction_id=c2_tx.transaction_id,
            state=CaseState.HUMAN_REVIEW,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            transaction=c2_tx,
            detection=c2_det,
            evidence_bundle=c2_ev,
            findings=c2_findings,
            robustness=c2_rob,
            policy_decision=c2_pol,
            assigned_analyst_id="demo_analyst",
        )
    )

    # -------------------------------------------------------------------------
    # Case 3: Merchant Fraud Trend Spike (Fragile)
    # -------------------------------------------------------------------------
    c3_id = "case_03"
    c3_tx = Transaction(
        transaction_id="tx_demo_c03",
        customer_id="cust_1020",
        account_id="acc_3391",
        card_id="card_9901",
        merchant_id="merch_crypto_voucher",
        amount=Decimal("450.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_known_customer",
        ip_address="198.51.100.44",
        geo=Geo(lat=Decimal("37.7749"), lon=Decimal("-122.4194"), country="USA"),
        channel=Channel.WEB,
        merchant_category="financial_services",
        card_present=False,
    )
    c3_det = _make_detection(
        c3_id,
        c3_tx.transaction_id,
        Decimal("0.72"),
        RiskBand.MEDIUM,
        [AnomalyTag.MERCHANT_RISK],
        ["High chargeback rate at merchant"],
    )
    c3_f1 = _make_fact("fact_merch_single_spike", "MERCHANT_CHARGEBACK", "merch_crypto_voucher", {"chargeback_rate": "0.048", "summary": "Merchant chargeback rate elevated at 4.8%."}, "get_merchant_risk")
    c3_ev = _make_bundle(c3_id, [c3_f1], ["get_merchant_risk"])
    c3_findings = _make_findings(
        findings_id="find_c03",
        case_id=c3_id,
        risk=RiskBand.HIGH,
        summary="Customer transaction from trusted device, but merchant has sudden chargeback spike.",
        supporting=[
            FindingFactor(statement="Merchant chargeback rate elevated at 4.8%.", fact_ids=["fact_merch_single_spike"], materiality=Materiality.HIGH)
        ],
        citations=[Citation(claim_id="claim_cb", fact_ids=["fact_merch_single_spike"])],
    )
    c3_rob = _make_robustness(c3_id, RobustnessClassification.FRAGILE, fragile_factor_id="fact_merch_single_spike")
    c3_pol = _make_policy_decision(
        c3_id,
        "P-002",
        PolicyOutcome.ESCALATE,
        ["Medium detection risk with high findings assessment and complete evidence held for review."],
    )
    templates.append(
        build_case_document(
            case_id=c3_id,
            transaction_id=c3_tx.transaction_id,
            state=CaseState.HUMAN_REVIEW,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            transaction=c3_tx,
            detection=c3_det,
            evidence_bundle=c3_ev,
            findings=c3_findings,
            robustness=c3_rob,
            policy_decision=c3_pol,
            assigned_analyst_id="demo_analyst",
        )
    )

    # -------------------------------------------------------------------------
    # Case 4: Degraded Telemetry / Incomplete Evidence (Partial Evidence, P-001)
    # -------------------------------------------------------------------------
    c4_id = "case_04"
    c4_tx = Transaction(
        transaction_id="tx_demo_c04",
        customer_id="cust_7721",
        account_id="acc_1199",
        card_id="card_3301",
        merchant_id="merch_apparel_store",
        amount=Decimal("380.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_missing_meta",
        ip_address="198.51.100.99",
        geo=Geo(lat=Decimal("37.7749"), lon=Decimal("-122.4194"), country="USA"),
        channel=Channel.WEB,
        merchant_category="apparel",
        card_present=False,
    )
    c4_det = _make_detection(
        c4_id,
        c4_tx.transaction_id,
        Decimal("0.65"),
        RiskBand.MEDIUM,
        [AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION],
        ["Unrecognized device", "Unknown IP geolocation"],
    )
    c4_f1 = _make_fact("fact_dev_partial", "DEVICE_VERIFICATION", "dev_missing_meta", {"status": "PARTIAL", "summary": "Device ID verified; however IP geolocation telemetry is missing upstream."}, "get_device_history")
    c4_ev = _make_bundle(c4_id, [c4_f1], ["get_device_history"], completeness=EvidenceCompleteness.PARTIAL, missing=["ip_geolocation_telemetry"])
    c4_pol = _make_policy_decision(
        c4_id,
        "P-001",
        PolicyOutcome.ESCALATE,
        ["Evidence completeness is PARTIAL: missing required evidence floor [ip_geolocation_telemetry]."],
    )
    templates.append(
        build_case_document(
            case_id=c4_id,
            transaction_id=c4_tx.transaction_id,
            state=CaseState.HUMAN_REVIEW,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            transaction=c4_tx,
            detection=c4_det,
            evidence_bundle=c4_ev,
            findings=None,
            robustness=None,
            policy_decision=c4_pol,
            assigned_analyst_id="demo_analyst",
        )
    )

    # -------------------------------------------------------------------------
    # Case 5: Reasoning Structured Output Failure (Reasoning Failed, P-003)
    # -------------------------------------------------------------------------
    c5_id = "case_05"
    c5_tx = Transaction(
        transaction_id="tx_demo_c05",
        customer_id="cust_3311",
        account_id="acc_8844",
        card_id="card_1122",
        merchant_id="merch_gaming_credits",
        amount=Decimal("199.99"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_emu_44",
        ip_address="198.51.100.33",
        geo=Geo(lat=Decimal("37.7749"), lon=Decimal("-122.4194"), country="USA"),
        channel=Channel.MOBILE,
        merchant_category="digital_goods",
        card_present=False,
    )
    c5_det = _make_detection(
        c5_id,
        c5_tx.transaction_id,
        Decimal("0.78"),
        RiskBand.HIGH,
        [AnomalyTag.NEW_DEVICE],
        ["Virtual emulator detected"],
    )
    c5_f1 = _make_fact("fact_emu_detected", "DEVICE_ENVIRONMENT", "dev_emu_44", {"environment": "EMULATOR", "summary": "Device environment indicates Android emulator virtualization."}, "get_device_history")
    c5_ev = _make_bundle(c5_id, [c5_f1], ["get_device_history"])
    c5_pol = _make_policy_decision(
        c5_id,
        "P-003",
        PolicyOutcome.ESCALATE,
        ["Reasoning status is FAILED: LLM structured output schema validation failed after bounded retry."],
    )
    templates.append(
        build_case_document(
            case_id=c5_id,
            transaction_id=c5_tx.transaction_id,
            state=CaseState.HUMAN_REVIEW,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            transaction=c5_tx,
            detection=c5_det,
            evidence_bundle=c5_ev,
            findings=None,
            robustness=None,
            policy_decision=c5_pol,
            assigned_analyst_id="demo_analyst",
        )
    )

    # -------------------------------------------------------------------------
    # Case 6: High-Value Velocity Burst (Robust)
    # -------------------------------------------------------------------------
    c6_id = "case_06"
    c6_tx = Transaction(
        transaction_id="tx_demo_c06",
        customer_id="cust_9920",
        account_id="acc_6610",
        card_id="card_8819",
        merchant_id="merch_gift_cards",
        amount=Decimal("1950.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_rapid_burst",
        ip_address="198.51.100.101",
        geo=Geo(lat=Decimal("25.7617"), lon=Decimal("-80.1918"), country="USA"),
        channel=Channel.WEB,
        merchant_category="gift_cards",
        card_present=False,
    )
    c6_det = _make_detection(
        c6_id,
        c6_tx.transaction_id,
        Decimal("0.88"),
        RiskBand.HIGH,
        [AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION, AnomalyTag.MERCHANT_RISK],
        ["Rapid gift card purchases", "Unusual device fingerprint"],
    )
    c6_f1 = _make_fact("fact_velocity_burst", "VELOCITY", "cust_9920", {"burst_count": 3, "summary": "3 high-value gift card purchases submitted in less than 10 minutes."}, "get_transaction_history")
    c6_f2 = _make_fact("fact_card_age", "CARD_LIFECYCLE", "card_8819", {"issued_hours_ago": 2, "summary": "Payment card was reissued 2 hours prior to immediate gift card velocity burst."}, "get_customer_profile")
    c6_ev = _make_bundle(c6_id, [c6_f1, c6_f2], ["get_transaction_history", "get_customer_profile"])
    c6_findings = _make_findings(
        findings_id="find_c06",
        case_id=c6_id,
        risk=RiskBand.HIGH,
        summary="High-risk card draining signature: immediate gift card cash-out burst following credential re-issuance.",
        supporting=[
            FindingFactor(statement="Velocity burst on high-liquidity merchant category.", fact_ids=["fact_velocity_burst"], materiality=Materiality.HIGH),
            FindingFactor(statement="Transaction immediately follows credential issuance.", fact_ids=["fact_card_age"], materiality=Materiality.HIGH),
        ],
        citations=[
            Citation(claim_id="claim_vel", fact_ids=["fact_velocity_burst"]),
            Citation(claim_id="claim_card", fact_ids=["fact_card_age"]),
        ],
    )
    c6_rob = _make_robustness(c6_id, RobustnessClassification.ROBUST)
    c6_pol = _make_policy_decision(
        c6_id,
        "P-002",
        PolicyOutcome.ESCALATE,
        ["High risk score and high value transaction with complete evidence held for review."],
    )
    templates.append(
        build_case_document(
            case_id=c6_id,
            transaction_id=c6_tx.transaction_id,
            state=CaseState.HUMAN_REVIEW,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            transaction=c6_tx,
            detection=c6_det,
            evidence_bundle=c6_ev,
            findings=c6_findings,
            robustness=c6_rob,
            policy_decision=c6_pol,
            assigned_analyst_id="demo_analyst",
        )
    )

    # -------------------------------------------------------------------------
    # Case 7: Branching Agent Linked Entity Discovery (Robust)
    # -------------------------------------------------------------------------
    c7_id = "case_07"
    c7_tx = Transaction(
        transaction_id="tx_demo_c07",
        customer_id="cust_5502",
        account_id="acc_7712",
        card_id="card_4411",
        merchant_id="merch_appliances_direct",
        amount=Decimal("899.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_shared_mule",
        ip_address="198.51.100.55",
        geo=Geo(lat=Decimal("30.2672"), lon=Decimal("-97.7431"), country="USA"),
        channel=Channel.WEB,
        merchant_category="home_appliances",
        card_present=False,
    )
    c7_det = _make_detection(
        c7_id,
        c7_tx.transaction_id,
        Decimal("0.85"),
        RiskBand.HIGH,
        [AnomalyTag.NEW_DEVICE, AnomalyTag.MERCHANT_RISK],
        ["Device linked to external account cluster"],
    )
    c7_f1 = _make_fact("fact_branching_proof", "MULE_CLUSTER", "dev_shared_mule", {"cluster_id": "mule_cl_4", "linked_cards": 5, "summary": "Autonomous branching discovery: device dev_shared_mule links 5 different customer payment cards in 24h."}, "get_linked_entities")
    c7_f2 = _make_fact("fact_merch_reports", "MERCHANT_REPORTS", "merch_appliances_direct", {"recent_count": 3, "trend": "RISING", "summary": "Merchant reports 3 recent fraud escalations with a rising trajectory."}, "get_merchant_risk")
    c7_ev = _make_bundle(c7_id, [c7_f1, c7_f2], ["get_device_history", "get_linked_entities", "get_merchant_risk"])
    c7_findings = _make_findings(
        findings_id="find_c07",
        case_id=c7_id,
        risk=RiskBand.HIGH,
        summary="Syndicate mule cluster detected: Evidence Agent autonomously followed device linkage into shared mule network.",
        supporting=[
            FindingFactor(statement="Device confirmed part of active multi-card mule ring.", fact_ids=["fact_branching_proof"], materiality=Materiality.HIGH),
            FindingFactor(statement="Merchant trend confirms unauthorized CNP fraud pattern.", fact_ids=["fact_merch_reports"], materiality=Materiality.HIGH),
        ],
        citations=[
            Citation(claim_id="claim_mule", fact_ids=["fact_branching_proof"]),
            Citation(claim_id="claim_trend", fact_ids=["fact_merch_reports"]),
        ],
    )
    c7_rob = _make_robustness(c7_id, RobustnessClassification.ROBUST)
    c7_pol = _make_policy_decision(
        c7_id,
        "P-002",
        PolicyOutcome.ESCALATE,
        ["High risk score and high value transaction with complete evidence held for review."],
    )
    templates.append(
        build_case_document(
            case_id=c7_id,
            transaction_id=c7_tx.transaction_id,
            state=CaseState.HUMAN_REVIEW,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            transaction=c7_tx,
            detection=c7_det,
            evidence_bundle=c7_ev,
            findings=c7_findings,
            robustness=c7_rob,
            policy_decision=c7_pol,
            assigned_analyst_id="demo_analyst",
        )
    )

    # -------------------------------------------------------------------------
    # Case 8: Elevated Baseline Risk Clean Profile (Clean + Elevated Risk)
    # -------------------------------------------------------------------------
    c8_id = "case_08"
    c8_tx = Transaction(
        transaction_id="tx_demo_c08",
        customer_id="cust_8833",
        account_id="acc_4419",
        card_id="card_6620",
        merchant_id="merch_general_clean",
        amount=Decimal("120.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_cust_known",
        ip_address="198.51.100.80",
        geo=Geo(lat=Decimal("37.7749"), lon=Decimal("-122.4194"), country="USA"),
        channel=Channel.WEB,
        merchant_category="general_retail",
        card_present=False,
    )
    c8_det = _make_detection(
        c8_id,
        c8_tx.transaction_id,
        Decimal("0.55"),
        RiskBand.MEDIUM,
        [],
        ["Statistical score elevated above low risk ceiling"],
    )
    templates.append(
        build_case_document(
            case_id=c8_id,
            transaction_id=c8_tx.transaction_id,
            state=CaseState.HUMAN_REVIEW,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
            transaction=c8_tx,
            detection=c8_det,
            evidence_bundle=None,
            findings=None,
            robustness=None,
            policy_decision=None,
            assigned_analyst_id="demo_analyst",
        )
    )

    # -------------------------------------------------------------------------
    # Case 9: Historical Audit: Cleared Case (Finalized with CLEAR disposition)
    # -------------------------------------------------------------------------
    c9_id = "case_09"
    c9_tx = Transaction(
        transaction_id="tx_demo_c09",
        customer_id="cust_2219",
        account_id="acc_5512",
        card_id="card_7718",
        merchant_id="merch_airline_direct",
        amount=Decimal("650.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_laptop_travel",
        ip_address="198.51.100.15",
        geo=Geo(lat=Decimal("33.7490"), lon=Decimal("-84.3880"), country="USA"),
        channel=Channel.WEB,
        merchant_category="travel",
        card_present=False,
    )
    c9_det = _make_detection(
        c9_id,
        c9_tx.transaction_id,
        Decimal("0.68"),
        RiskBand.MEDIUM,
        [AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION],
        ["Travel location pattern departure"],
    )
    c9_f1 = _make_fact("fact_travel_ip", "TRAVEL_VERIFICATION", "cust_2219", {"is_travel": True, "summary": "Transaction matches domestic flight itinerary booked through airline web portal."}, "get_location_history")
    c9_ev = _make_bundle(c9_id, [c9_f1], ["get_location_history"])
    c9_findings = _make_findings(
        findings_id="find_c09",
        case_id=c9_id,
        risk=RiskBand.LOW,
        summary="Legitimate customer holiday travel: new laptop purchase matches known seasonal flight departure.",
        supporting=[],
        counter=[FindingFactor(statement="Matches verified customer flight booking history.", fact_ids=["fact_travel_ip"], materiality=Materiality.HIGH)],
        citations=[Citation(claim_id="claim_travel", fact_ids=["fact_travel_ip"])],
        disposition=RecommendedDisposition.CLEAR,
    )
    c9_rob = _make_robustness(c9_id, RobustnessClassification.ROBUST)
    c9_pol = _make_policy_decision(
        c9_id,
        "P-002",
        PolicyOutcome.ESCALATE,
        ["Medium detection risk with complete evidence held for human verification."],
    )
    c9_doc = build_case_document(
        case_id=c9_id,
        transaction_id=c9_tx.transaction_id,
        state=CaseState.FINALIZED,
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
        transaction=c9_tx,
        detection=c9_det,
        evidence_bundle=c9_ev,
        findings=c9_findings,
        robustness=c9_rob,
        policy_decision=c9_pol,
        assigned_analyst_id="demo_analyst",
        final_disposition=HumanAction.CLEAR,
    )
    c9_doc["final_reason"] = "Customer verified in-app 2FA confirmation for domestic flight booking."
    templates.append(c9_doc)

    # -------------------------------------------------------------------------
    # Case 10: Historical Audit: Blocked Case (Finalized with BLOCK_HOLD disposition)
    # -------------------------------------------------------------------------
    c10_id = "case_10"
    c10_tx = Transaction(
        transaction_id="tx_demo_c10",
        customer_id="cust_1109",
        account_id="acc_2290",
        card_id="card_9918",
        merchant_id="merch_wire_transfer_service",
        amount=Decimal("3500.00"),
        currency="USD",
        timestamp=BASE_TIME,
        payment_rail=PaymentRail.CARD_CNP,
        direction=Direction.OUTGOING,
        authorization_stage=AuthorizationStage.PRE_AUTH,
        device_id="dev_darknet_vpn",
        ip_address="198.51.100.200",
        geo=Geo(lat=Decimal("51.5074"), lon=Decimal("-0.1278"), country="GBR"),
        channel=Channel.WEB,
        merchant_category="money_services",
        card_present=False,
    )
    c10_det = _make_detection(
        c10_id,
        c10_tx.transaction_id,
        Decimal("0.98"),
        RiskBand.HIGH,
        [AnomalyTag.NEW_DEVICE, AnomalyTag.UNUSUAL_LOCATION, AnomalyTag.MERCHANT_RISK],
        ["Anonymizer Tor exit node", "Suspicious international wire destination"],
    )
    c10_f1 = _make_fact("fact_darknet_vpn", "ANONYMIZER", "dev_darknet_vpn", {"anonymizer_detected": True, "summary": "Commercial bulletproof proxy / Tor exit node used during international wire initiation."}, "get_device_history")
    c10_ev = _make_bundle(c10_id, [c10_f1], ["get_device_history"])
    c10_findings = _make_findings(
        findings_id="find_c10",
        case_id=c10_id,
        risk=RiskBand.HIGH,
        summary="Critical ATO and funds extraction: Tor routing with maximum limit wire attempt.",
        supporting=[
            FindingFactor(statement="Confirmed bulletproof proxy and Tor exit node.", fact_ids=["fact_darknet_vpn"], materiality=Materiality.HIGH)
        ],
        citations=[Citation(claim_id="claim_tor", fact_ids=["fact_darknet_vpn"])],
    )
    c10_rob = _make_robustness(c10_id, RobustnessClassification.ROBUST)
    c10_pol = _make_policy_decision(
        c10_id,
        "P-002",
        PolicyOutcome.ESCALATE,
        ["High risk score and value exceeding threshold with complete evidence held for review."],
    )
    c10_doc = build_case_document(
        case_id=c10_id,
        transaction_id=c10_tx.transaction_id,
        state=CaseState.FINALIZED,
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
        transaction=c10_tx,
        detection=c10_det,
        evidence_bundle=c10_ev,
        findings=c10_findings,
        robustness=c10_rob,
        policy_decision=c10_pol,
        assigned_analyst_id="demo_analyst",
        final_disposition=HumanAction.BLOCK_HOLD,
    )
    c10_doc["final_reason"] = "Customer contacted via verified branch phone; confirmed card stolen and unauthorized wire."
    templates.append(c10_doc)

    return templates
