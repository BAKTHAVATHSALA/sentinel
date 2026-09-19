"""Deterministic Policy evaluator for Sentinel V1 -- the sole automated
disposition authority (Contracts V1-Scoped S15/S16, Build Checklist
Phase 4.1).

`evaluate_policy` is a pure function: given a case's inputs, it returns
exactly one PolicyDecision whose outcome is AUTO_RESOLVE or ESCALATE, never
anything else -- PolicyOutcome's enum has no third member, so this is a
type-level guarantee, not just a runtime one. No path in this module ever
constructs or returns the string "BLOCK_HOLD".

## risk_score vs risk_band

Contracts V1-Scoped S16 writes the rules in terms of `risk_score >= HIGH`,
`>= MEDIUM`, `<= LOW`. Rather than re-deriving those boundaries here as a
second copy of the cutoffs, this evaluator compares against
`detection.risk_band` directly: risk_band is computed by
shared.detection.model.RiskScoringModel using exactly LOW_RISK_THRESHOLD/
HIGH_RISK_THRESHOLD, so "risk_score >= HIGH" is definitionally
"risk_band == HIGH", "risk_score >= MEDIUM" is "risk_band != LOW", and
"risk_score <= LOW" is "risk_band == LOW". Comparing bands avoids a second,
independently-drifting copy of the same threshold logic.

## reasoning.status = FAILED

There is no explicit "reasoning failed" rule in the frozen contract.
findings is None whenever ReasoningOutput.status = FAILED (Contracts
V1-Scoped S16); every named rule below that needs findings.risk_assessment
treats a None findings as not matching, so a failed reasoning call falls
through to the Otherwise rule -> ESCALATE, exactly matching Safety
Invariant 10 ("an unhandled failure ... results in ESCALATED, never a
silent AUTO_RESOLVED").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from shared.contracts.detection import DetectionOutput, RiskBand
from shared.contracts.evidence import EvidenceBundle, EvidenceCompleteness
from shared.contracts.policy import PolicyDecision
from shared.contracts.reasoning import CaseFindings, ReasoningOutput, ReasoningStatus
from shared.contracts.transaction import Transaction
from shared.policy.constants import HARD_RISK_TAGS
from shared.policy.rules import POLICY_RULES
from shared.policy.thresholds import HIGH_VALUE_THRESHOLD


@dataclass(frozen=True)
class _PolicyContext:
    """Everything one Policy evaluation may read, resolved once per call."""

    transaction: Transaction
    detection: DetectionOutput
    evidence_bundle: EvidenceBundle
    reasoning_output: ReasoningOutput

    @property
    def findings(self) -> CaseFindings | None:
        if self.reasoning_output.status != ReasoningStatus.SUCCESS:
            return None
        return self.reasoning_output.findings

    @property
    def completeness(self) -> EvidenceCompleteness:
        return self.evidence_bundle.completeness

    @property
    def hard_risk_tags_present(self) -> tuple[str, ...]:
        present = set(self.detection.anomaly_tags) & set(HARD_RISK_TAGS)
        return tuple(sorted(tag.value for tag in present))


def _rule_p001(ctx: _PolicyContext) -> bool:
    return ctx.completeness == EvidenceCompleteness.PARTIAL


def _rule_p002(ctx: _PolicyContext) -> bool:
    return (
        ctx.detection.risk_band != RiskBand.LOW  # "risk_score >= MEDIUM"
        and ctx.findings is not None
        and ctx.findings.risk_assessment == RiskBand.HIGH
        and ctx.completeness == EvidenceCompleteness.COMPLETE
    )


def _rule_p003(ctx: _PolicyContext) -> bool:
    return (
        ctx.detection.risk_band == RiskBand.HIGH  # "risk_score >= HIGH"
        and ctx.transaction.amount >= HIGH_VALUE_THRESHOLD
        and ctx.completeness == EvidenceCompleteness.COMPLETE
    )


def _rule_p004(ctx: _PolicyContext) -> bool:
    # v1.3 amendment (Contracts S0.1/S6.3/S16): auto-resolve requires a
    # CLEAN transaction -- zero anomaly tags of any kind -- not merely the
    # absence of a HARD_RISK_TAGS member. A statistical tag (NEW_DEVICE,
    # UNUSUAL_LOCATION, UNUSUAL_AMOUNT) now blocks auto-resolve exactly like
    # a structural tag does; LOW risk_band alone is necessary but no longer
    # sufficient. This is a strict narrowing of the old condition, so any
    # transaction excluded before (a HARD_RISK_TAGS member) is still
    # excluded now -- Safety Invariant 6 holds a fortiori.
    return (
        ctx.detection.risk_band == RiskBand.LOW  # "risk_score <= LOW"
        and ctx.completeness == EvidenceCompleteness.COMPLETE
        and not ctx.detection.anomaly_tags
        and ctx.findings is not None
        and ctx.findings.risk_assessment != RiskBand.HIGH
    )


def _rule_otherwise(ctx: _PolicyContext) -> bool:  # noqa: ARG001 -- uniform predicate signature
    return True


_RULE_PREDICATES: dict[str, Callable[[_PolicyContext], bool]] = {
    "P-001": _rule_p001,
    "P-002": _rule_p002,
    "P-003": _rule_p003,
    "P-004": _rule_p004,
    "P-005": _rule_otherwise,
}


def _build_reasons(rule_id: str, ctx: _PolicyContext) -> list[str]:
    if rule_id == "P-001":
        return [f"evidence.completeness = {ctx.completeness.value} (Rule P-001 requires COMPLETE)"]
    if rule_id == "P-002":
        return [
            f"risk_band = {ctx.detection.risk_band.value} (>= MEDIUM)",
            f"findings.risk_assessment = {ctx.findings.risk_assessment.value}",  # type: ignore[union-attr]
            "evidence.completeness = COMPLETE",
        ]
    if rule_id == "P-003":
        return [
            f"risk_band = {ctx.detection.risk_band.value} (HIGH)",
            f"amount = {ctx.transaction.amount} >= HIGH_VALUE_THRESHOLD = {HIGH_VALUE_THRESHOLD}",
            "evidence.completeness = COMPLETE",
        ]
    if rule_id == "P-004":
        return [
            f"risk_band = {ctx.detection.risk_band.value} (LOW)",
            "evidence.completeness = COMPLETE",
            "anomaly_tags = [] (transaction is clean)",
            f"findings.risk_assessment = {ctx.findings.risk_assessment.value} (!= HIGH)",  # type: ignore[union-attr]
        ]
    # P-005 (Otherwise)
    reasons = ["No named rule (P-001..P-004) matched; forced-escalation default"]
    if ctx.findings is None:
        reasons.append(f"reasoning.status = {ctx.reasoning_output.status.value} -- no CaseFindings available")
    if ctx.detection.anomaly_tags and not ctx.hard_risk_tags_present:
        reasons.append(
            f"anomaly_tags present: {[tag.value for tag in ctx.detection.anomaly_tags]} "
            "-- Rule P-004 requires a clean transaction (zero anomaly tags) to auto-resolve"
        )
    if ctx.hard_risk_tags_present:
        reasons.append(f"HARD_RISK_TAGS present: {list(ctx.hard_risk_tags_present)}")
    return reasons


def _build_inputs_snapshot(ctx: _PolicyContext) -> dict[str, object]:
    return {
        "risk_score": str(ctx.detection.risk_score),
        "risk_band": ctx.detection.risk_band.value,
        "amount": str(ctx.transaction.amount),
        "currency": ctx.transaction.currency,
        "high_value_threshold": str(HIGH_VALUE_THRESHOLD),
        "evidence_completeness": ctx.completeness.value,
        "missing_required_evidence": list(ctx.evidence_bundle.missing_required_evidence),
        "anomaly_tags": [tag.value for tag in ctx.detection.anomaly_tags],
        "hard_risk_tags_present": list(ctx.hard_risk_tags_present),
        "reasoning_status": ctx.reasoning_output.status.value,
        "findings_risk_assessment": (ctx.findings.risk_assessment.value if ctx.findings is not None else None),
    }


def evaluate_policy(
    case_id: str,
    transaction: Transaction,
    detection: DetectionOutput,
    evidence_bundle: EvidenceBundle,
    reasoning_output: ReasoningOutput,
) -> PolicyDecision:
    """Evaluate Sentinel V1's frozen Policy rules and return exactly one PolicyDecision.

    Pure function: walks shared.policy.rules.POLICY_RULES in priority order and
    returns on the first enabled rule whose predicate matches. The Otherwise
    rule (P-005) has an unconditionally true predicate, so this always
    terminates with a match -- outcome is always AUTO_RESOLVE or ESCALATE.

    :param case_id: Case identifier this decision belongs to.
    :param transaction: The Transaction under investigation (amount is not
        carried by DetectionOutput/EvidenceBundle/CaseFindings, so it is
        threaded in directly, the same pattern used for ReasoningInput in
        Phase 3).
    :param detection: DetectionOutput for this case.
    :param evidence_bundle: EvidenceBundle gathered by the Evidence Agent.
    :param reasoning_output: ReasoningOutput from Reasoning (status +
        optional CaseFindings).
    :return: PolicyDecision recording rule_id, rule_version, reasons, and
        inputs_snapshot (Safety Invariant 7).
    """
    ctx = _PolicyContext(
        transaction=transaction,
        detection=detection,
        evidence_bundle=evidence_bundle,
        reasoning_output=reasoning_output,
    )

    for rule in POLICY_RULES:
        if not rule.enabled:
            continue
        predicate = _RULE_PREDICATES[rule.rule_id]
        if predicate(ctx):
            return PolicyDecision(
                decision_id=f"pd_{case_id}",
                case_id=case_id,
                outcome=rule.outcome,
                rule_id=rule.rule_id,
                rule_version=rule.version,
                reasons=_build_reasons(rule.rule_id, ctx),
                inputs_snapshot=_build_inputs_snapshot(ctx),
                evaluated_at=datetime.now(timezone.utc),
            )

    # Unreachable: P-005 (Otherwise) is always enabled with an
    # unconditionally true predicate, so the loop above always returns.
    raise AssertionError("[evaluate_policy] - no Policy rule matched; P-005 (Otherwise) must always match")
