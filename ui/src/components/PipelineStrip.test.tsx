import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PipelineStrip } from "./PipelineStrip";
import { cleanCase, flaggedFragileCase, reasoningFailedCase } from "../test/fixtures";

describe("PipelineStrip", () => {
  it("shows the escalated/fragile pipeline for a real flagged case", () => {
    render(<PipelineStrip caseDoc={flaggedFragileCase} />);
    expect(screen.getByText("Medium risk")).toBeInTheDocument();
    expect(screen.getByText("Fragile")).toBeInTheDocument();
    expect(screen.getByText("Escalate")).toBeInTheDocument();
    expect(screen.getByText("Awaiting")).toBeInTheDocument();
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
