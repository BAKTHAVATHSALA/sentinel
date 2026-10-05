/**
 * TypeScript mirrors of Sentinel V1's real backend contracts
 * (shared/contracts/*.py, shared/persistence/case_document.py,
 * services/api/cases.py). Every field here corresponds exactly to a real
 * Pydantic field name and serialized JSON type -- nothing invented.
 *
 * Serialization notes (pydantic model_dump(mode="json")):
 *   - Decimal -> string (amount, risk_score -- never parse these as float
 *     for display; render the string directly so precision is exact)
 *   - datetime -> ISO 8601 string
 *   - Enum -> its string value
 */

export type RiskBand = "LOW" | "MEDIUM" | "HIGH";
export type AnomalyTag =
  | "NEW_DEVICE"
  | "UNUSUAL_LOCATION"
  | "UNUSUAL_AMOUNT"
  | "MERCHANT_RISK"
  | "LINKED_ENTITY_ANOMALY"
  | "KYC_ANOMALY"
  | "IMPOSSIBLE_TRAVEL"
  | "UNUSUAL_TIME";

export type FactQuality = "VERIFIED" | "DERIVED" | "PARTIAL";
export type EvidenceCompleteness = "COMPLETE" | "PARTIAL";
export type Materiality = "HIGH" | "MEDIUM" | "LOW";
export type RecommendedDisposition = "CLEAR" | "ESCALATE" | "BLOCK_HOLD";
export type RobustnessClassification = "ROBUST" | "FRAGILE";
export type RobustnessMethod = "FAST_PATH" | "LIVE_COUNTERFACTUAL";
export type PolicyOutcome = "AUTO_RESOLVE" | "ESCALATE";
export type HumanAction = "CLEAR" | "BLOCK_HOLD" | "ESCALATE_SENIOR";
export type ReasoningStatus = "SUCCESS" | "FAILED";

export type CaseState =
  | "RECEIVED"
  | "DETECTED"
  | "FLAGGED"
  | "INVESTIGATING"
  | "EVIDENCE_READY"
  | "EVIDENCE_PARTIAL"
  | "REASONED"
  | "REASONING_FAILED"
  | "POLICY_EVALUATED"
  | "AUTO_RESOLVED"
  | "ESCALATED"
  | "HUMAN_REVIEW"
  | "FINALIZED";

export interface Geo {
  lat: string;
  lon: string;
  country: string;
}

export interface Transaction {
  transaction_id: string;
  customer_id: string;
  account_id: string;
  card_id: string;
  merchant_id: string;
  amount: string;
  currency: string;
  timestamp: string;
  payment_rail: string;
  direction: string;
  authorization_stage: "PRE_AUTH" | "AUTH" | "SETTLED";
  device_id: string;
  ip_address: string;
  geo: Geo;
  channel: "WEB" | "MOBILE";
  merchant_category: string;
  card_present: boolean;
}

export interface DetectionOutput {
  case_id: string;
  transaction_id: string;
  risk_score: string;
  risk_band: RiskBand;
  anomaly_tags: AnomalyTag[];
  detection_reasons: string[];
  model_name: string;
  model_version: string;
  detected_at: string;
}

export interface Fact {
  fact_id: string;
  type: string;
  subject_id: string;
  value: Record<string, unknown>;
  source_tool: string;
  source_record_id: string | null;
  observed_at: string;
  retrieved_at: string;
  quality: FactQuality;
}

export interface EvidenceBundle {
  evidence_bundle_id: string;
  case_id: string;
  facts: Fact[];
  tools_called: string[];
  required_tools: string[];
  completeness: EvidenceCompleteness;
  missing_required_evidence: string[];
  conflicts: string[];
  started_at: string;
  completed_at: string;
}

export interface FindingFactor {
  statement: string;
  fact_ids: string[];
  materiality: Materiality;
}

export interface Citation {
  claim_id: string;
  fact_ids: string[];
}

export interface CaseFindings {
  findings_id: string;
  case_id: string;
  risk_assessment: RiskBand;
  summary: string;
  supporting_factors: FindingFactor[];
  counter_factors: FindingFactor[];
  evidence_gaps: string[];
  evidence_citations: Citation[];
  recommended_disposition: RecommendedDisposition;
  generated_at: string;
  model_name: string;
  model_version: string;
  prompt_version: string;
}

export interface RobustnessResult {
  robustness_id: string;
  case_id: string;
  classification: RobustnessClassification;
  fragile_factor_id: string | null;
  method: RobustnessMethod;
  evaluated_at: string;
}

export interface PolicyDecision {
  decision_id: string;
  case_id: string;
  outcome: PolicyOutcome;
  rule_id: string;
  rule_version: string;
  reasons: string[];
  inputs_snapshot: Record<string, unknown>;
  evaluated_at: string;
}

/** One escalation-target option for the senior-selection dropdown (V1
 * Authoritative Ruling Part 4: name/email shown, raw UID never displayed). */
export interface SeniorOption {
  uid: string;
  display_name: string;
  email: string;
}

/** Response-only, non-persisted counterfactual re-evaluation (Addendum 1
 * Point 4), present only when `?simulate_without=` was supplied. */
export interface CounterfactualResult {
  removed_fact_id: string;
  findings: CaseFindings | null;
  robustness: RobustnessResult;
  policy_outcome_would_change: boolean;
}

/** GET /cases/{case_id} -- the full cases/{case_id} document, unmodified.
 * `available_seniors` is present only when the case is HUMAN_REVIEW and the
 * caller is an ANALYST -- its presence is also how the UI knows, without a
 * separate "who am I" endpoint, whether to show the escalate control at all
 * (role is server-resolved and never trusted/re-derived client-side). */
export interface CaseDocument {
  case_id: string;
  transaction_id: string;
  state: CaseState;
  created_at: string;
  updated_at: string;
  transaction: Transaction;
  detection: DetectionOutput;
  evidence_bundle: EvidenceBundle | null;
  findings: CaseFindings | null;
  robustness: RobustnessResult | null;
  policy_decision: PolicyDecision | null;
  assigned_analyst_id: string | null;
  final_disposition: HumanAction | null;
  available_seniors?: SeniorOption[];
  counterfactual?: CounterfactualResult;
}

/** GET /cases -- one row of the queue view. `final_disposition` and
 * `is_escalated_by_me` are additive fields, present on every row regardless
 * of `?scope` (defaulted on the plain queue view, where they are always
 * null/false since that view only ever returns open, non-escalated cases).
 * `is_escalated_by_me` is a backend-computed boolean, never a raw analyst
 * UID -- it says only "you escalated this case", nothing about who holds it
 * now (see services/api/cases.py:list_cases). */
export interface QueueCaseSummary {
  case_id: string;
  transaction_id: string;
  state: CaseState;
  created_at: string;
  updated_at: string;
  amount: string;
  currency: string;
  merchant_id: string;
  risk_band: RiskBand;
  anomaly_tags: AnomalyTag[];
  robustness_classification: RobustnessClassification | null;
  robustness_fragile_factor_id: string | null;
  final_disposition: HumanAction | null;
  is_escalated_by_me: boolean;
}

/** POST /cases/{case_id}/decision request body. `target_analyst_id` is used
 * only for ESCALATE_SENIOR -- the selected senior's Firebase UID (V1
 * Authoritative Ruling Part 4). `analyst_id` is always the caller's own UID;
 * the backend verifies it against the authenticated session and rejects a
 * mismatch, it never trusts it as an actor identity by itself. */
export interface HumanDecisionRequest {
  case_id: string;
  analyst_id: string;
  action: HumanAction;
  reason: string | null;
  evidence_acknowledged: boolean;
  client_timestamp: string;
  target_analyst_id?: string | null;
}

/** POST /cases/{case_id}/decision response. `final_disposition` is null for
 * ESCALATE_SENIOR (a reassignment, not a finalization -- state stays
 * HUMAN_REVIEW); `assigned_analyst_id` reflects the post-decision owner
 * (a raw Firebase UID -- a transport value, never rendered as visible text).
 * `target_analyst_display_name` is additive (Q11 verification fix): set only
 * for a successful ESCALATE_SENIOR, so the confirmation screen can show a
 * name without ever calling GET /cases/{case_id} again. */
export interface DecisionResponse {
  case_id: string;
  state: CaseState;
  final_disposition: HumanAction | null;
  assigned_analyst_id: string | null;
  decided_at: string;
  idempotent_replay: boolean;
  target_analyst_display_name: string | null;
}

/** The normal round-robin ANALYST a case was routed to, public/judge-facing
 * (Transaction Console): display name only -- no email, no Firebase UID, no
 * role. The same shape `run_pipeline`'s `_analyst_summary` builds, and it is
 * restricted server-side to `role === "ANALYST"`: a case reassigned to a
 * SENIOR_ANALYST via the existing ESCALATE_SENIOR workflow is never surfaced
 * here, even on a duplicate-transaction lookup -- that identity is visible
 * only inside the authenticated, case-scoped Analyst Portal. */
export interface AssignmentSummary {
  analyst_name: string;
}

/** Public-safe decision summary for the Transaction Console (additive
 * POST /transactions response field, `shared/pipeline/orchestrator.py:
 * _decision_summary` / `_decision_summary_from_document`) -- built entirely
 * from real, already-computed pipeline objects, never inferred or recreated
 * by the frontend. Deliberately excludes protected case content: no raw
 * evidence facts, no Gemini findings summary/citations, no robustness
 * detail, no exact merchant financial figures (only the `merchant_flagged`
 * boolean), no analyst email/UID. */
export interface DecisionSummary {
  risk_assessment: RiskBand | null;
  anomaly_tags: AnomalyTag[];
  policy_rule_id: string | null;
  reasons: string[];
  evidence_completeness: EvidenceCompleteness | null;
  merchant_flagged: boolean;
}

/** POST /transactions response -- the orchestrator's real, un-typed return
 * dict (shared/pipeline/orchestrator.py:run_pipeline), not a frozen
 * `shared/contracts` class. This is the ONLY shape the Transaction Console
 * ever reads; it never calls GET /cases/{case_id}. `outcome`/`rule_id` are
 * null for a clean transaction that skipped investigation entirely;
 * `assignment` is non-null only when `state === "HUMAN_REVIEW"` and
 * round-robin found an active normal ANALYST (null if unassigned, or if the
 * case's current owner is a SENIOR_ANALYST). */
export interface TransactionInvestigationResult {
  case_id: string;
  transaction_id: string;
  state: CaseState;
  outcome: PolicyOutcome | null;
  rule_id: string | null;
  duplicate: boolean;
  assignment: AssignmentSummary | null;
  decision_summary: DecisionSummary;
}

/** GET /transactions/{transaction_id}/status response (services/api/main.py:
 * TransactionStatusResponse) -- the Transaction Console's poll target while
 * POST /transactions for this transaction_id is still in flight. `case_id`/
 * `state` are null until the pipeline's first Firestore write lands; the
 * three `has_*` booleans are the only signal of downstream progress --
 * never the evidence/robustness/policy content itself. */
export interface TransactionLiveStatus {
  case_id: string | null;
  state: CaseState | null;
  has_evidence_bundle: boolean;
  has_robustness: boolean;
  has_policy_decision: boolean;
}
