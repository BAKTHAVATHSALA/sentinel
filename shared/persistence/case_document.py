"""Firestore `cases/{case_id}` document shape for Sentinel V1 (Build
Checklist Phase 4.2: "transaction, detection, evidence_bundle, findings,
robustness, policy_decision, state, assigned_analyst_id").

This is a richer, denormalized persistence document, not a re-statement of
the frozen `Case` contract (Contracts V1-Scoped S5) -- Case only carries
`evidence_bundle_id`/`findings_id`/`policy_decision_id` foreign-key-style
references, deliberately thin. The checklist's Firestore document shape
embeds the full nested objects instead, so the analyst UI (Phase 5) and the
queue view can read one case in a single document fetch rather than four.
Nothing here redefines the Case contract itself; shared.contracts.case.Case
is untouched.

All decimal/enum/datetime fields go through `model_dump(mode="json")` so
Firestore stores JSON-safe values (in particular, Decimal amounts as
strings, never float, to avoid precision loss).
"""

from __future__ import annotations

from datetime import datetime

from shared.contracts.case import CaseState, HumanAction
from shared.contracts.detection import DetectionOutput
from shared.contracts.evidence import EvidenceBundle
from shared.contracts.policy import PolicyDecision
from shared.contracts.reasoning import CaseFindings
from shared.contracts.robustness import RobustnessResult
from shared.contracts.transaction import Transaction


def build_case_document(
    case_id: str,
    transaction_id: str,
    state: CaseState,
    created_at: datetime,
    updated_at: datetime,
    transaction: Transaction,
    detection: DetectionOutput,
    evidence_bundle: EvidenceBundle | None = None,
    findings: CaseFindings | None = None,
    robustness: RobustnessResult | None = None,
    policy_decision: PolicyDecision | None = None,
    assigned_analyst_id: str | None = None,
    final_disposition: HumanAction | None = None,
) -> dict[str, object]:
    """Build the JSON-safe Firestore document for one case.

    :param case_id: Case identifier (Firestore document ID).
    :param transaction_id: Transaction this case investigates.
    :param state: Current CaseState.
    :param created_at: When the case was first created.
    :param updated_at: When this document version was written.
    :param transaction: The Transaction under investigation.
    :param detection: DetectionOutput for this case.
    :param evidence_bundle: EvidenceBundle, once the Evidence Agent has run.
    :param findings: CaseFindings, once Reasoning has succeeded.
    :param robustness: RobustnessResult, once the Robustness Scorer has run.
    :param policy_decision: PolicyDecision, once Policy has evaluated the case.
    :param assigned_analyst_id: Analyst currently assigned, if any.
    :param final_disposition: Human analyst's final action, if any (Phase 5).
    :return: A plain dict safe to pass directly to a Firestore document write.
    """
    return {
        "case_id": case_id,
        "transaction_id": transaction_id,
        "state": state.value,
        "created_at": created_at,
        "updated_at": updated_at,
        "transaction": transaction.model_dump(mode="json"),
        "detection": detection.model_dump(mode="json"),
        "evidence_bundle": evidence_bundle.model_dump(mode="json") if evidence_bundle else None,
        "findings": findings.model_dump(mode="json") if findings else None,
        "robustness": robustness.model_dump(mode="json") if robustness else None,
        "policy_decision": policy_decision.model_dump(mode="json") if policy_decision else None,
        "assigned_analyst_id": assigned_analyst_id,
        "final_disposition": final_disposition.value if final_disposition else None,
    }
