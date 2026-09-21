import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CaseHeader } from "./CaseHeader";
import { flaggedFragileCase, cleanCase, finalizedCase } from "../test/fixtures";

describe("CaseHeader", () => {
  it("shows case state, risk, amount, merchant, and signals from real data", () => {
    render(<CaseHeader caseDoc={flaggedFragileCase} />);
    expect(screen.getByText("HUMAN REVIEW")).toBeInTheDocument();
    expect(screen.getByText("Medium")).toBeInTheDocument(); // RiskBadge label for MEDIUM
    expect(screen.getByText("$75.00")).toBeInTheDocument();
    expect(screen.getByText("merch_standard_branch")).toBeInTheDocument();
    expect(screen.getByText("New device")).toBeInTheDocument();
  });

  it("preserves transaction metadata (device/location/card/channel) as a secondary row", () => {
    render(<CaseHeader caseDoc={flaggedFragileCase} />);
    expect(screen.getByText("dev_branch_shared_77428")).toBeInTheDocument();
    expect(screen.getByText("USA")).toBeInTheDocument();
    expect(screen.getByText("WEB")).toBeInTheDocument();
  });

  it("does not show anomaly signals when there are none", () => {
    render(<CaseHeader caseDoc={cleanCase} />);
    expect(screen.queryByText("New device")).not.toBeInTheDocument();
  });

  it("renders AUTO_RESOLVED state without a critical/red color", () => {
    render(<CaseHeader caseDoc={cleanCase} />);
    const stateEl = screen.getByText("AUTO RESOLVED");
    expect(stateEl.className).not.toContain("critical");
  });

  it("renders a FINALIZED/CLEAR state without a critical/red color", () => {
    expect(finalizedCase.final_disposition).toBe("CLEAR");
    render(<CaseHeader caseDoc={finalizedCase} />);
    const stateEl = screen.getByText("FINALIZED");
    expect(stateEl.className).not.toContain("critical");
  });

  it("renders a FINALIZED/BLOCK_HOLD state in red -- the one case red is correct for", () => {
    render(<CaseHeader caseDoc={{ ...finalizedCase, final_disposition: "BLOCK_HOLD" }} />);
    const stateEl = screen.getByText("FINALIZED");
    expect(stateEl.className).toContain("critical");
  });
});
