import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { InvestigationResultPanel } from "./InvestigationResultPanel";
import type { Transaction, TransactionInvestigationResult } from "../lib/types";

const TRANSACTION: Transaction = {
  transaction_id: "tx_1",
  customer_id: "cust_1",
  account_id: "acc_1",
  card_id: "card_1",
  merchant_id: "merch_1",
  amount: "59.00",
  currency: "USD",
  timestamp: "2026-09-19T14:00:00Z",
  payment_rail: "CARD_CNP",
  direction: "OUTGOING",
  authorization_stage: "PRE_AUTH",
  device_id: "dev_1",
  ip_address: "1.2.3.4",
  geo: { lat: "0", lon: "0", country: "USA" },
  channel: "WEB",
  merchant_category: "electronics",
  card_present: false,
};

// Reflects the real, live backend shape: a genuinely clean AUTO_RESOLVE
// skips investigation entirely, so policy_rule_id/reasons/evidence_completeness
// are null in the real response, not "P-004".
const AUTO_RESOLVE_RESULT: TransactionInvestigationResult = {
  case_id: "case_clean_1",
  transaction_id: "tx_1",
  state: "AUTO_RESOLVED",
  outcome: null,
  rule_id: null,
  duplicate: false,
  assignment: null,
  decision_summary: {
    risk_assessment: "LOW",
    anomaly_tags: [],
    policy_rule_id: null,
    reasons: [],
    evidence_completeness: null,
    merchant_flagged: false,
  },
};

const HUMAN_REVIEW_RESULT: TransactionInvestigationResult = {
  case_id: "case_escalated_1",
  transaction_id: "tx_1",
  state: "HUMAN_REVIEW",
  outcome: "ESCALATE",
  rule_id: "P-002",
  duplicate: false,
  assignment: { analyst_name: "Grace Okafor" },
  decision_summary: {
    risk_assessment: "HIGH",
    anomaly_tags: ["NEW_DEVICE", "UNUSUAL_LOCATION"],
    policy_rule_id: "P-002",
    reasons: ["risk_band = HIGH (>= MEDIUM)", "findings.risk_assessment = HIGH", "evidence.completeness = COMPLETE"],
    evidence_completeness: "COMPLETE",
    merchant_flagged: false,
  },
};

// LOW risk + a statistical anomaly tag: not auto-resolve-eligible even
// though risk is LOW (v1.3 P-004 semantics).
const LOW_RISK_ANOMALOUS_HUMAN_REVIEW_RESULT: TransactionInvestigationResult = {
  case_id: "case_low_anomalous_1",
  transaction_id: "tx_1",
  state: "HUMAN_REVIEW",
  outcome: "ESCALATE",
  rule_id: "P-005",
  duplicate: false,
  assignment: { analyst_name: "Marcus Webb" },
  decision_summary: {
    risk_assessment: "LOW",
    anomaly_tags: ["NEW_DEVICE"],
    policy_rule_id: "P-005",
    reasons: ["No named rule (P-001..P-004) matched; forced-escalation default"],
    evidence_completeness: "COMPLETE",
    merchant_flagged: false,
  },
};

// CLEAN (zero anomaly tags) but MEDIUM/HIGH risk: still not auto-resolve
// eligible (risk_score <= LOW is required alongside anomaly_tags = []).
// This path skips investigation entirely -- evidence_completeness stays
// null even though the disposition is HUMAN_REVIEW.
const CLEAN_BUT_ELEVATED_RISK_HUMAN_REVIEW_RESULT: TransactionInvestigationResult = {
  case_id: "case_clean_elevated_1",
  transaction_id: "tx_1",
  state: "HUMAN_REVIEW",
  outcome: null,
  rule_id: null,
  duplicate: false,
  assignment: { analyst_name: "Priya Nair" },
  decision_summary: {
    risk_assessment: "HIGH",
    anomaly_tags: [],
    policy_rule_id: null,
    reasons: [],
    evidence_completeness: null,
    merchant_flagged: false,
  },
};

function renderPanel(result: TransactionInvestigationResult) {
  return render(
    <MemoryRouter>
      <InvestigationResultPanel phase="done" result={result} transaction={TRANSACTION} />
    </MemoryRouter>,
  );
}

describe("InvestigationResultPanel -- AUTO_RESOLVED", () => {
  it("shows a large AUTO-RESOLVED heading and the fixed clean-transaction copy, with NO prominent risk label", () => {
    renderPanel(AUTO_RESOLVE_RESULT);

    expect(screen.getByText("AUTO-RESOLVED")).toBeInTheDocument();
    expect(screen.getByText("No anomalies found")).toBeInTheDocument();
    expect(screen.getAllByText("No analyst action required.").length).toBeGreaterThan(0);
    expect(screen.getByText("No anomaly signals detected.")).toBeInTheDocument();
    expect(screen.getByText("Required automated investigation checks completed.")).toBeInTheDocument();

    // E: no prominent risk label anywhere, even though the backend still
    // returns risk_assessment=LOW internally.
    expect(screen.queryByText(/LOW RISK/)).not.toBeInTheDocument();
    expect(screen.queryByText(/RISK$/)).not.toBeInTheDocument();
  });

  it("H: never shows analyst assignment or an Open Case link", () => {
    renderPanel(AUTO_RESOLVE_RESULT);
    expect(screen.queryByText("Assigned to:")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open Case" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Grace Okafor|Priya Nair|Marcus Webb/)).not.toBeInTheDocument();
  });

  it("never exposes policy_rule_id, raw policy reason strings, or an expandable Policy Details section", () => {
    renderPanel({
      ...AUTO_RESOLVE_RESULT,
      rule_id: "P-004",
      decision_summary: { ...AUTO_RESOLVE_RESULT.decision_summary, policy_rule_id: "P-004", reasons: ["risk_band = LOW (LOW)"] },
    });
    expect(screen.queryByText("P-004")).not.toBeInTheDocument();
    expect(screen.queryByText(/risk_band = LOW/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Policy Details/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Policy rule/i)).not.toBeInTheDocument();
  });

  it("never shows anomaly signal chips or a merchant-flagged note (there are none for a clean result)", () => {
    renderPanel(AUTO_RESOLVE_RESULT);
    expect(screen.queryByText("Signals:")).not.toBeInTheDocument();
    expect(screen.queryByText(/Merchant flagged/)).not.toBeInTheDocument();
  });

  it("G: never shows HUMAN_REVIEW-only copy", () => {
    renderPanel(AUTO_RESOLVE_RESULT);
    expect(screen.queryByText("HUMAN REVIEW")).not.toBeInTheDocument();
    expect(screen.queryByText("Analyst investigation required.")).not.toBeInTheDocument();
    expect(screen.queryByText("Investigation status:")).not.toBeInTheDocument();
  });
});

describe("InvestigationResultPanel -- HUMAN_REVIEW", () => {
  it("F: shows a large HUMAN REVIEW heading and the actual risk assessment prominently", () => {
    renderPanel(HUMAN_REVIEW_RESULT);
    expect(screen.getByText("HUMAN REVIEW")).toBeInTheDocument();
    expect(screen.getByText("HIGH RISK")).toBeInTheDocument();
    expect(screen.getByText("Analyst investigation required.")).toBeInTheDocument();
  });

  it("shows the real anomaly signals and the full investigation-status checklist when actually investigated", () => {
    renderPanel(HUMAN_REVIEW_RESULT);
    expect(screen.getByText("New device")).toBeInTheDocument();
    expect(screen.getByText("Unusual location")).toBeInTheDocument();
    expect(screen.getByText("Detection complete")).toBeInTheDocument();
    expect(screen.getByText("Evidence collected")).toBeInTheDocument();
    expect(screen.getByText("AI reasoning complete")).toBeInTheDocument();
    expect(screen.getByText("Routed for human review")).toBeInTheDocument();
    expect(screen.getByText("Grace Okafor")).toBeInTheDocument();
  });

  it("G: never shows AUTO_RESOLVED-only copy -- this was the exact reported bug (HUMAN REVIEW displaying AUTO_RESOLVED explanation text)", () => {
    renderPanel(HUMAN_REVIEW_RESULT);
    expect(screen.queryByText("Why this was resolved:")).not.toBeInTheDocument();
    expect(screen.queryByText(/automatic resolution/)).not.toBeInTheDocument();
    expect(screen.queryByText("No analyst action required.")).not.toBeInTheDocument();
    expect(screen.queryByText("AUTO-RESOLVED")).not.toBeInTheDocument();
    expect(screen.queryByText("No anomalies found")).not.toBeInTheDocument();
  });

  it("also never shows AUTO_RESOLVED-only copy for a LOW-risk anomalous result (regression case for the exact reported bug)", () => {
    renderPanel(LOW_RISK_ANOMALOUS_HUMAN_REVIEW_RESULT);
    expect(screen.getByText("HUMAN REVIEW")).toBeInTheDocument();
    expect(screen.getByText("LOW RISK")).toBeInTheDocument();
    expect(screen.getByText("New device")).toBeInTheDocument();
    expect(screen.queryByText("Why this was resolved:")).not.toBeInTheDocument();
    expect(screen.queryByText(/automatic resolution/)).not.toBeInTheDocument();
    expect(screen.queryByText("No analyst action required.")).not.toBeInTheDocument();
    expect(screen.queryByText("No anomaly signals detected.")).not.toBeInTheDocument();
    expect(screen.queryByText("P-005")).not.toBeInTheDocument();
  });

  it("handles a CLEAN-but-elevated-risk HUMAN_REVIEW case honestly: no investigation-only claims, no false 'no anomaly' framing", () => {
    renderPanel(CLEAN_BUT_ELEVATED_RISK_HUMAN_REVIEW_RESULT);
    expect(screen.getByText("HUMAN REVIEW")).toBeInTheDocument();
    expect(screen.getByText("HIGH RISK")).toBeInTheDocument();
    expect(screen.getByText("Priya Nair")).toBeInTheDocument();
    // Never investigated -- must not claim Evidence/Reasoning ran.
    expect(screen.queryByText("Evidence collected")).not.toBeInTheDocument();
    expect(screen.queryByText("AI reasoning complete")).not.toBeInTheDocument();
    expect(screen.getByText("Detection complete")).toBeInTheDocument();
    expect(screen.getByText("Routed for human review")).toBeInTheDocument();
    // Still never claims AUTO_RESOLVED copy despite anomaly_tags being empty.
    expect(screen.queryByText("Why this was resolved:")).not.toBeInTheDocument();
    expect(screen.queryByText("No analyst action required.")).not.toBeInTheDocument();
    expect(screen.queryByText("No anomalies found")).not.toBeInTheDocument();
  });

  it("never exposes policy_rule_id or raw policy reason strings", () => {
    renderPanel(HUMAN_REVIEW_RESULT);
    expect(screen.queryByText("P-002")).not.toBeInTheDocument();
    expect(screen.queryByText(/risk_band = HIGH \(>= MEDIUM\)/)).not.toBeInTheDocument();
    expect(screen.queryByText(/findings\.risk_assessment = HIGH/)).not.toBeInTheDocument();
    expect(screen.queryByText(/evidence\.completeness = COMPLETE/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Policy Details/i)).not.toBeInTheDocument();
  });

  it("keeps Open Case as the primary next step, linking to the protected case route", () => {
    renderPanel(HUMAN_REVIEW_RESULT);
    const link = screen.getByRole("link", { name: "Open Case" });
    expect(link).toHaveAttribute("href", "/case/case_escalated_1");
  });

  it("shows the merchant-flagged note only when the backend says merchant_flagged is true", () => {
    renderPanel({
      ...HUMAN_REVIEW_RESULT,
      decision_summary: { ...HUMAN_REVIEW_RESULT.decision_summary, merchant_flagged: true },
    });
    expect(screen.getByText(/Merchant flagged as elevated risk/)).toBeInTheDocument();
  });

  it("never renders protected case content (raw evidence, findings text, robustness, UID)", () => {
    renderPanel(HUMAN_REVIEW_RESULT);
    expect(screen.queryByText(/supporting_factors/)).not.toBeInTheDocument();
    expect(screen.queryByText(/counter_factors/)).not.toBeInTheDocument();
    expect(screen.queryByText(/tools_called/)).not.toBeInTheDocument();
    expect(screen.queryByText(/ROBUST|FRAGILE/)).not.toBeInTheDocument();
    expect(screen.queryByText(/@sentinel\.demo/)).not.toBeInTheDocument();
  });
});
