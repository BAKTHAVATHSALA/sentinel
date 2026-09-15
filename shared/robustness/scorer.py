"""Decision Robustness Scorer for Sentinel V1 (Contracts v1.2 S18, Build
Checklist Phase 3.3).

Two independent paths, matching the frozen contract exactly:

- fast_path(): the default, every-case estimate (S18.1). For each
  HIGH-materiality supporting factor, estimate whether removing it alone
  would flip risk_assessment below the Policy escalation threshold. The
  threshold this scorer reasons about is findings.risk_assessment reaching
  HIGH -- the only band Policy rule P-004 (Contracts v1.2 S20) keys
  escalation off of via findings.risk_assessment. A single HIGH-materiality
  factor is, by this estimate, the sole driver of a HIGH assessment
  (FRAGILE); two or more mean any one factor's removal still leaves another
  sustaining it (ROBUST). This is a structural estimate over CaseFindings --
  it never calls Gemini.
- live_counterfactual(): the real demo path (S18.2). Given a specific
  fact_id, rebuild the EvidenceBundle without it and re-invoke Reasoning for
  real, then classify from what Gemini actually returns the second time.

RobustnessResult.classification is investigative/UI signal only -- never
wired into Policy (S18.3).
"""

from __future__ import annotations

from datetime import datetime, timezone

from shared.contracts.detection import RiskBand
from shared.contracts.evidence import EvidenceBundle
from shared.contracts.reasoning import CaseFindings, Materiality, ReasoningInput, ReasoningStatus
from shared.contracts.robustness import RobustnessClassification, RobustnessMethod, RobustnessResult
from shared.reasoning.service import ReasoningService

# Contracts v1.2 S18.1/S20: the Policy escalation threshold this scorer
# reasons about is findings.risk_assessment reaching HIGH (Policy rule
# P-004 keys escalation off exactly that band).
ESCALATION_THRESHOLD = RiskBand.HIGH


def rebuild_evidence_bundle_without_fact(evidence_bundle: EvidenceBundle, fact_id: str) -> EvidenceBundle:
    """Rebuild an EvidenceBundle with one fact removed, for a live counterfactual re-call.

    :param evidence_bundle: The original EvidenceBundle Reasoning saw.
    :param fact_id: fact_id to remove for this counterfactual.
    :return: A new EvidenceBundle, identical except facts excludes fact_id.
    """
    return evidence_bundle.model_copy(
        update={
            "evidence_bundle_id": f"{evidence_bundle.evidence_bundle_id}_cf_{fact_id}",
            "facts": [f for f in evidence_bundle.facts if f.fact_id != fact_id],
        }
    )


class RobustnessScorer:
    """Runs the fast-path estimate and the live counterfactual re-call."""

    def __init__(self, reasoning_service: ReasoningService) -> None:
        """Initialize with an injected ReasoningService for the live counterfactual path.

        :param reasoning_service: Live ReasoningService, re-invoked for real by
            live_counterfactual(). fast_path() never calls it.
        """
        self._reasoning_service = reasoning_service

    def fast_path(self, case_id: str, findings: CaseFindings) -> RobustnessResult:
        """Estimate ROBUST/FRAGILE from CaseFindings alone, without calling Gemini.

        :param case_id: Case identifier this result belongs to.
        :param findings: The case's validated, citation-clean CaseFindings.
        :return: RobustnessResult with method=FAST_PATH.
        """
        robustness_id = f"rob_{case_id}_fastpath"
        if findings.risk_assessment != ESCALATION_THRESHOLD:
            # Nothing to flip "below" the threshold: the assessment is
            # already not at/above it, so no single factor's removal is
            # estimated to move it further below what Policy already
            # treats as escalatable via findings.risk_assessment.
            return self._result(
                robustness_id, case_id, RobustnessClassification.ROBUST, None, RobustnessMethod.FAST_PATH
            )

        high_factors = [f for f in findings.supporting_factors if f.materiality == Materiality.HIGH]
        if len(high_factors) >= 2:
            return self._result(
                robustness_id, case_id, RobustnessClassification.ROBUST, None, RobustnessMethod.FAST_PATH
            )

        if len(high_factors) == 1:
            sole_factor = high_factors[0]
            fragile_factor_id = sole_factor.fact_ids[0] if sole_factor.fact_ids else None
            return self._result(
                robustness_id,
                case_id,
                RobustnessClassification.FRAGILE,
                fragile_factor_id,
                RobustnessMethod.FAST_PATH,
            )

        # HIGH assessment with zero HIGH-materiality supporting factors: no
        # single factor's removal is, by this estimate, the sole driver.
        return self._result(
            robustness_id, case_id, RobustnessClassification.ROBUST, None, RobustnessMethod.FAST_PATH
        )

    def live_counterfactual(
        self,
        case_id: str,
        reasoning_input: ReasoningInput,
        fact_id_to_remove: str,
    ) -> RobustnessResult:
        """Rebuild the evidence bundle without one fact and re-invoke Reasoning for real.

        This is the live demo path (Contracts v1.2 S18.2) -- not an estimate.
        A reasoning.status=FAILED counterfactual re-call is itself classified
        FRAGILE: "removing this fact breaks Reasoning's ability to produce a
        valid, cited assessment at all" is evidence the original assessment
        was not robust to that fact's absence, not a reason to discard the
        counterfactual result (RobustnessResult stays advisory-only per
        S18.3, so this never feeds an automated decision).

        :param case_id: Case identifier this result belongs to.
        :param reasoning_input: The original ReasoningInput whose evidence_bundle will be
            rebuilt without fact_id_to_remove.
        :param fact_id_to_remove: fact_id to drop before re-invoking Reasoning.
        :return: RobustnessResult with method=LIVE_COUNTERFACTUAL.
        """
        counterfactual_bundle = rebuild_evidence_bundle_without_fact(
            reasoning_input.evidence_bundle, fact_id_to_remove
        )
        counterfactual_input = reasoning_input.model_copy(update={"evidence_bundle": counterfactual_bundle})

        output = self._reasoning_service.reason(counterfactual_input)

        if output.status == ReasoningStatus.FAILED or output.findings is None:
            classification = RobustnessClassification.FRAGILE
        elif output.findings.risk_assessment != ESCALATION_THRESHOLD:
            classification = RobustnessClassification.FRAGILE
        else:
            classification = RobustnessClassification.ROBUST

        fragile_factor_id = fact_id_to_remove if classification == RobustnessClassification.FRAGILE else None
        robustness_id = f"rob_{case_id}_cf_{fact_id_to_remove}"
        return self._result(robustness_id, case_id, classification, fragile_factor_id, RobustnessMethod.LIVE_COUNTERFACTUAL)

    @staticmethod
    def _result(
        robustness_id: str,
        case_id: str,
        classification: RobustnessClassification,
        fragile_factor_id: str | None,
        method: RobustnessMethod,
    ) -> RobustnessResult:
        return RobustnessResult(
            robustness_id=robustness_id,
            case_id=case_id,
            classification=classification,
            fragile_factor_id=fragile_factor_id,
            method=method,
            evaluated_at=datetime.now(timezone.utc),
        )
