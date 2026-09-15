import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceCompletenessBadge, RiskBadge, RobustnessBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders a text label for every risk band, never color alone", () => {
    render(<RiskBadge band="HIGH" />);
    expect(screen.getByText("High")).toBeInTheDocument();
  });

  it("labels FRAGILE and ROBUST distinctly with text", () => {
    render(<RobustnessBadge classification="FRAGILE" supportingCount={1} />);
    expect(screen.getByText("Fragile")).toBeInTheDocument();

    render(<RobustnessBadge classification="ROBUST" supportingCount={2} />);
    expect(screen.getByText("Robust")).toBeInTheDocument();
  });

  it("labels evidence completeness with text", () => {
    render(<EvidenceCompletenessBadge completeness="PARTIAL" />);
    expect(screen.getByText("Partial")).toBeInTheDocument();
  });
});
