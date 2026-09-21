import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InvestigationSummary } from "./InvestigationSummary";
import { flaggedFragileCase } from "../test/fixtures";

describe("InvestigationSummary", () => {
  it("shows the AI assessment risk band, framed as advisory and never as a recommendation to act", () => {
    render(<InvestigationSummary findings={flaggedFragileCase.findings!} />);
    expect(screen.getByText("AI assessment", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText(/Advisory \(not the policy decision\)/)).toBeInTheDocument();
  });

  it("never says Gemini 'recommends' an action -- Policy, not Gemini, controls routing", () => {
    render(<InvestigationSummary findings={flaggedFragileCase.findings!} />);
    expect(screen.queryByText(/recommends/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Escalate")).not.toBeInTheDocument();
  });

  it("lists the real supporting factors, counter-evidence, and evidence gaps", () => {
    render(<InvestigationSummary findings={flaggedFragileCase.findings!} />);
    expect(screen.getByText("Supporting factors")).toBeInTheDocument();
    expect(screen.getByText("Device shared with another account.")).toBeInTheDocument();
    expect(screen.getByText("Counter-evidence")).toBeInTheDocument();
    expect(screen.getByText("Evidence gaps")).toBeInTheDocument();
  });

  it("shows 'None' for an empty category rather than omitting it silently", () => {
    render(<InvestigationSummary findings={{ ...flaggedFragileCase.findings!, counter_factors: [], evidence_gaps: [] }} />);
    const noneEls = screen.getAllByText("None");
    expect(noneEls.length).toBe(2);
  });

  it("never fabricates a statement not present in findings", () => {
    render(<InvestigationSummary findings={flaggedFragileCase.findings!} />);
    expect(screen.queryByText(/lorem ipsum/i)).not.toBeInTheDocument();
  });
});
