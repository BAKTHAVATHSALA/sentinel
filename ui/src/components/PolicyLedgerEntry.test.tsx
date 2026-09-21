import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { PolicyLedgerEntry } from "./PolicyLedgerEntry";
import type { PolicyDecision } from "../lib/types";

const ESCALATE_DECISION: PolicyDecision = {
  decision_id: "pd_1",
  case_id: "case_1",
  outcome: "ESCALATE",
  rule_id: "P-002",
  rule_version: "1.1.0",
  reasons: ["risk_band = MEDIUM (>= MEDIUM)", "findings.risk_assessment = HIGH"],
  inputs_snapshot: { hard_risk_tags_present: ["MERCHANT_RISK"] },
  evaluated_at: "2026-09-21T00:00:00Z",
};

const AUTO_RESOLVE_DECISION: PolicyDecision = {
  ...ESCALATE_DECISION,
  outcome: "AUTO_RESOLVE",
  rule_id: "P-004",
  inputs_snapshot: {},
};

describe("PolicyLedgerEntry", () => {
  it("shows the compact HUMAN REVIEW label and plain-English sentence for ESCALATE, in amber (not red)", () => {
    render(<PolicyLedgerEntry decision={ESCALATE_DECISION} />);
    const label = screen.getByText("HUMAN REVIEW");
    expect(label).toBeInTheDocument();
    expect(label).toHaveStyle({ color: "var(--color-caution)" });
    expect(screen.getByText("Human investigation required.")).toBeInTheDocument();
  });

  it("never uses red/critical for a successful ESCALATE outcome", () => {
    render(<PolicyLedgerEntry decision={ESCALATE_DECISION} />);
    const label = screen.getByText("HUMAN REVIEW");
    expect(label).not.toHaveStyle({ color: "var(--color-critical)" });
  });

  it("shows the compact AUTO-RESOLVED label for AUTO_RESOLVE, in teal/stable", () => {
    render(<PolicyLedgerEntry decision={AUTO_RESOLVE_DECISION} />);
    const label = screen.getByText("AUTO-RESOLVED");
    expect(label).toHaveStyle({ color: "var(--color-stable)" });
    expect(screen.getByText("No analyst action required.")).toBeInTheDocument();
  });

  it("hides rule_id, rule_version, reasons, and hard-risk tags by default", () => {
    render(<PolicyLedgerEntry decision={ESCALATE_DECISION} />);
    expect(screen.queryByText("P-002")).not.toBeInTheDocument();
    expect(screen.queryByText(/risk_band = MEDIUM/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Hard-risk tags/)).not.toBeInTheDocument();
  });

  it("expands to reveal rule_id, rule_version, exact reasons, and hard-risk tags", async () => {
    const user = userEvent.setup();
    render(<PolicyLedgerEntry decision={ESCALATE_DECISION} />);

    await user.click(screen.getByRole("button", { name: "Policy details" }));

    expect(screen.getByText("P-002")).toBeInTheDocument();
    expect(screen.getByText("v1.1.0")).toBeInTheDocument();
    expect(screen.getByText("risk_band = MEDIUM (>= MEDIUM)")).toBeInTheDocument();
    expect(screen.getByText(/Hard-risk tags: MERCHANT_RISK/)).toBeInTheDocument();
  });

  it("does not show a hard-risk tags line when none are present", async () => {
    const user = userEvent.setup();
    render(<PolicyLedgerEntry decision={AUTO_RESOLVE_DECISION} />);
    await user.click(screen.getByRole("button", { name: "Policy details" }));
    expect(screen.queryByText(/Hard-risk tags/)).not.toBeInTheDocument();
  });
});
