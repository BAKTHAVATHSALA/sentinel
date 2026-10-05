import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { deriveJourneyNodes, InvestigationJourney } from "./InvestigationJourney";
import type { TransactionInvestigationResult, TransactionLiveStatus } from "../lib/types";

function liveStatus(overrides: Partial<TransactionLiveStatus>): TransactionLiveStatus {
  return {
    case_id: "case_live",
    state: null,
    has_evidence_bundle: false,
    has_robustness: false,
    has_policy_decision: false,
    ...overrides,
  };
}

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

  describe("with real polled liveStatus while running (GET /transactions/{id}/status)", () => {
    function byLabel(nodes: ReturnType<typeof deriveJourneyNodes>) {
      return Object.fromEntries(nodes.map((n) => [n.label, n.state]));
    }

    it("shows only Detection active before the pipeline's first Firestore write lands", () => {
      const nodes = deriveJourneyNodes("running", null, liveStatus({ case_id: null, state: null }));
      const b = byLabel(nodes);
      expect(b["Transaction"]).toBe("complete");
      expect(b["Detection"]).toBe("active");
      expect(b["Evidence Agent"]).toBe("waiting");
    });

    it("advances to Evidence Agent active once Detection has run (state=DETECTED)", () => {
      const nodes = deriveJourneyNodes("running", null, liveStatus({ state: "DETECTED" }));
      const b = byLabel(nodes);
      expect(b["Detection"]).toBe("complete");
      expect(b["Evidence Agent"]).toBe("active");
      expect(b["AI Reasoning"]).toBe("waiting");
    });

    it("advances to AI Reasoning active once evidence is ready", () => {
      const nodes = deriveJourneyNodes("running", null, liveStatus({ state: "EVIDENCE_READY", has_evidence_bundle: true }));
      const b = byLabel(nodes);
      expect(b["Evidence Agent"]).toBe("complete");
      expect(b["AI Reasoning"]).toBe("active");
      expect(b["Robustness"]).toBe("waiting");
    });

    it("treats EVIDENCE_PARTIAL the same as EVIDENCE_READY for progression -- Reasoning still runs on partial evidence", () => {
      const nodes = deriveJourneyNodes("running", null, liveStatus({ state: "EVIDENCE_PARTIAL", has_evidence_bundle: true }));
      const b = byLabel(nodes);
      expect(b["Evidence Agent"]).toBe("complete");
      expect(b["AI Reasoning"]).toBe("active");
    });

    it("advances to Robustness active once Reasoning succeeds", () => {
      const nodes = deriveJourneyNodes(
        "running",
        null,
        liveStatus({ state: "REASONED", has_evidence_bundle: true }),
      );
      const b = byLabel(nodes);
      expect(b["AI Reasoning"]).toBe("complete");
      expect(b["Robustness"]).toBe("active");
      expect(b["Policy"]).toBe("waiting");
    });

    it("advances to Policy active once Robustness is scored", () => {
      const nodes = deriveJourneyNodes(
        "running",
        null,
        liveStatus({ state: "REASONED", has_evidence_bundle: true, has_robustness: true }),
      );
      const b = byLabel(nodes);
      expect(b["Robustness"]).toBe("complete");
      expect(b["Policy"]).toBe("active");
      expect(b["Routing"]).toBe("waiting");
    });

    it("advances to Routing active once Policy has decided", () => {
      const nodes = deriveJourneyNodes(
        "running",
        null,
        liveStatus({
          state: "POLICY_EVALUATED",
          has_evidence_bundle: true,
          has_robustness: true,
          has_policy_decision: true,
        }),
      );
      const b = byLabel(nodes);
      expect(b["Policy"]).toBe("complete");
      expect(b["Routing"]).toBe("active");
    });

    it("marks AI Reasoning as a real failure (error) while still letting Policy/Routing run -- Sentinel's fail-safe Policy still decides", () => {
      const nodes = deriveJourneyNodes(
        "running",
        null,
        liveStatus({ state: "REASONING_FAILED", has_evidence_bundle: true }),
      );
      const b = byLabel(nodes);
      expect(b["AI Reasoning"]).toBe("error");
      expect(b["Robustness"]).toBe("skipped");
      expect(b["Policy"]).toBe("active");
    });

    it("shows a clean transaction's investigation stages as skipped (not complete) while still routing, never claiming Policy ran", () => {
      const nodes = deriveJourneyNodes("running", null, liveStatus({ state: "AUTO_RESOLVED", has_policy_decision: false }));
      const b = byLabel(nodes);
      expect(b["Evidence Agent"]).toBe("skipped");
      expect(b["AI Reasoning"]).toBe("skipped");
      expect(b["Policy"]).toBe("skipped");
      expect(b["Routing"]).toBe("complete");
    });

    it("shows a clean-but-elevated-risk escalation as still routing (not complete) while ESCALATED, never fabricating investigation stages", () => {
      const nodes = deriveJourneyNodes("running", null, liveStatus({ state: "ESCALATED", has_policy_decision: false }));
      const b = byLabel(nodes);
      expect(b["Evidence Agent"]).toBe("skipped");
      expect(b["Policy"]).toBe("skipped");
      expect(b["Routing"]).toBe("active"); // not HUMAN_REVIEW yet
    });

    it("marks every investigated stage complete once a real investigation reaches HUMAN_REVIEW", () => {
      const nodes = deriveJourneyNodes(
        "running",
        null,
        liveStatus({ state: "HUMAN_REVIEW", has_evidence_bundle: true, has_robustness: true, has_policy_decision: true }),
      );
      expect(nodes.every((n) => n.state === "complete")).toBe(true);
    });

    it("falls back to the simultaneous-pulse display when no liveStatus has landed yet (e.g. first render, or an older backend)", () => {
      const nodes = deriveJourneyNodes("running", null, null);
      expect(nodes[0].state).toBe("complete");
      expect(nodes.slice(1).every((n) => n.state === "active")).toBe(true);
    });
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
