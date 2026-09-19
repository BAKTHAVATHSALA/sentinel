import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PipelineStrip } from "./PipelineStrip";
import { cleanCase, flaggedFragileCase, reasoningFailedCase } from "../test/fixtures";

const GREEN = "text-[var(--color-stable)]";
const AMBER = "text-[var(--color-caution)]";
const RED = "text-[var(--color-critical)]";

describe("PipelineStrip", () => {
  it("shows the escalated/fragile pipeline for a real flagged case", () => {
    render(<PipelineStrip caseDoc={flaggedFragileCase} />);
    expect(screen.getByText("Medium risk")).toBeInTheDocument();
    expect(screen.getByText("Fragile")).toBeInTheDocument();
    expect(screen.getByText("Escalate")).toBeInTheDocument();
    expect(screen.getByText("Awaiting")).toBeInTheDocument();
  });

  it("Phase E: renders Detection/Evidence/Reasoning/Robustness/Policy as GREEN/completed for a normal HUMAN_REVIEW case, with only Human Decision amber -- Policy ESCALATE is a successful completion, not a failure", () => {
    render(<PipelineStrip caseDoc={flaggedFragileCase} />);

    expect(screen.getByText("Medium risk").className).toContain(GREEN); // Detection
    expect(screen.getByText("Complete").className).toContain(GREEN); // Evidence
    expect(screen.getByText("Success").className).toContain(GREEN); // Reasoning (advisory, but completed)
    expect(screen.getByText("Fragile").className).toContain(GREEN); // Robustness (advisory, but completed)
    expect(screen.getByText("Escalate").className).toContain(GREEN); // Policy -- ESCALATE is a successful decision, not red
    expect(screen.getByText("Awaiting").className).toContain(AMBER); // Human Decision -- the only stage still pending

    expect(screen.getByText("Escalate").className).not.toContain(RED);
    expect(screen.getByText("Medium risk").className).not.toContain(RED);
  });

  it("Phase E: renders the terminal stage GREEN/completed for a real AUTO_RESOLVED (clean) case, with no red anywhere", () => {
    render(<PipelineStrip caseDoc={cleanCase} />);
    expect(screen.getByText("Low risk").className).toContain(GREEN); // Detection
    expect(screen.getByText("No action needed").className).toContain(GREEN); // automated resolution completed
    expect(screen.getByText("No action needed").className).not.toContain(RED);
  });

  it("Phase E: RED is reserved for a genuine technical failure (Reasoning actually failed), never for HIGH risk or HUMAN_REVIEW itself", () => {
    render(<PipelineStrip caseDoc={reasoningFailedCase} />);
    expect(screen.getByText("Failed").className).toContain(RED); // the one real failure in this fixture
    expect(screen.getByText("Medium risk").className).toContain(GREEN); // Detection still green -- risk band is not a failure
  });

  it("marks Evidence/Reasoning/Robustness skipped for a clean auto-resolved case", () => {
    render(<PipelineStrip caseDoc={cleanCase} />);
    expect(screen.getAllByText("Not required").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("No action needed")).toBeInTheDocument();
  });

  it("shows Reasoning failed and Robustness not scored when reasoning failed", () => {
    render(<PipelineStrip caseDoc={reasoningFailedCase} />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Not scored")).toBeInTheDocument();
  });
});
