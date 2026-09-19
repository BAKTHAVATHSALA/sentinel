import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { deriveJourneyNodes, InvestigationJourney } from "./InvestigationJourney";
import type { TransactionInvestigationResult } from "../lib/types";

const AUTO_RESOLVE: TransactionInvestigationResult = {
  case_id: "case_1",
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

const HUMAN_REVIEW: TransactionInvestigationResult = {
  case_id: "case_2",
  transaction_id: "tx_2",
  state: "HUMAN_REVIEW",
  outcome: "ESCALATE",
  rule_id: "P-002",
  duplicate: false,
  assignment: { analyst_name: "Priya Nair" },
  decision_summary: {
    risk_assessment: "HIGH",
    anomaly_tags: ["NEW_DEVICE"],
    policy_rule_id: "P-002",
    reasons: ["risk_band = HIGH (>= MEDIUM)", "findings.risk_assessment = HIGH", "evidence.completeness = COMPLETE"],
    evidence_completeness: "COMPLETE",
    merchant_flagged: false,
  },
};

describe("deriveJourneyNodes", () => {
  it("shows every node waiting before anything is submitted", () => {
    const nodes = deriveJourneyNodes("idle", null);
    expect(nodes.every((n) => n.state === "waiting")).toBe(true);
  });

  it("marks every stage after Transaction as active while the real request is in flight -- never a fake per-stage timeline", () => {
    const nodes = deriveJourneyNodes("running", null);
    expect(nodes[0].state).toBe("complete");
    expect(nodes.slice(1).every((n) => n.state === "active")).toBe(true);
  });

  it("marks a clean (non-investigated) AUTO_RESOLVE result's Evidence/Reasoning/Robustness/Policy as skipped, not complete", () => {
    const nodes = deriveJourneyNodes("done", AUTO_RESOLVE);
    const byLabel = Object.fromEntries(nodes.map((n) => [n.label, n.state]));
    expect(byLabel["Detection"]).toBe("complete");
    expect(byLabel["Evidence Agent"]).toBe("skipped");
    expect(byLabel["AI Reasoning"]).toBe("skipped");
    expect(byLabel["Robustness"]).toBe("skipped");
    expect(byLabel["Policy"]).toBe("skipped");
    expect(byLabel["Routing"]).toBe("complete");
  });

  it("marks every stage complete for an investigated HUMAN_REVIEW result", () => {
    const nodes = deriveJourneyNodes("done", HUMAN_REVIEW);
    expect(nodes.every((n) => n.state === "complete")).toBe(true);
  });

  it("marks a CLEAN-but-elevated-risk HUMAN_REVIEW result's investigation stages as skipped, not complete -- Policy never ran (outcome is null) for this path either", () => {
    const cleanButElevatedRisk: TransactionInvestigationResult = {
      ...HUMAN_REVIEW,
      outcome: null,
      rule_id: null,
      decision_summary: { ...HUMAN_REVIEW.decision_summary, anomaly_tags: [], policy_rule_id: null, evidence_completeness: null },
    };
    const nodes = deriveJourneyNodes("done", cleanButElevatedRisk);
    const byLabel = Object.fromEntries(nodes.map((n) => [n.label, n.state]));
    expect(byLabel["Detection"]).toBe("complete");
    expect(byLabel["Evidence Agent"]).toBe("skipped");
    expect(byLabel["Policy"]).toBe("skipped");
    expect(byLabel["Routing"]).toBe("complete"); // still routed, just to HUMAN_REVIEW instead of AUTO_RESOLVED
  });

  it("marks stages as error when the request itself failed", () => {
    const nodes = deriveJourneyNodes("request-failed", null);
    expect(nodes[0].state).toBe("complete");
    expect(nodes.slice(1).every((n) => n.state === "error")).toBe(true);
  });
});

describe("InvestigationJourney", () => {
  it("renders all 7 stage labels", () => {
    render(<InvestigationJourney phase="idle" result={null} />);
    for (const label of ["Transaction", "Detection", "Evidence Agent", "AI Reasoning", "Robustness", "Policy", "Routing"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });
});
