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

/** GET /cases/{case_id} -- the full cases/{case_id} document, unmodified. */
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
}

/** GET /cases -- one row of the queue view. */
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
}

/** POST /cases/{case_id}/decision request body. */
export interface HumanDecisionRequest {
  case_id: string;
  analyst_id: string;
  action: HumanAction;
  reason: string | null;
  evidence_acknowledged: boolean;
  client_timestamp: string;
}

/** POST /cases/{case_id}/decision response. */
export interface DecisionResponse {
  case_id: string;
  state: CaseState;
  final_disposition: HumanAction;
  decided_at: string;
  idempotent_replay: boolean;
}
