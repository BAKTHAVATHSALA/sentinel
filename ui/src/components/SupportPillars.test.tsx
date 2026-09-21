import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CitationThreadProvider } from "./CitationThread";
import { SupportPillars } from "./SupportPillars";
import { flaggedFragileCase } from "../test/fixtures";

const exhibitNumbers: Record<string, number> = {};
flaggedFragileCase.evidence_bundle!.facts.forEach((f, i) => (exhibitNumbers[f.fact_id] = i + 1));

function renderPillars() {
  return render(
    <CitationThreadProvider>
      <SupportPillars robustness={flaggedFragileCase.robustness!} findings={flaggedFragileCase.findings!} exhibitNumbers={exhibitNumbers} />
    </CitationThreadProvider>,
  );
}

describe("SupportPillars", () => {
  it("shows the classification badge and a fixed compact summary sentence by default (fixture is FRAGILE)", () => {
    renderPillars();
    expect(screen.getByText("Fragile")).toBeInTheDocument();
    expect(screen.getByText("Assessment would not survive removing a single evidence factor.")).toBeInTheDocument();
    expect(screen.getByText("Fast-path")).toBeInTheDocument();
  });

  it("hides the detailed factor-count explanation and fragile-factor citation by default", () => {
    renderPillars();
    expect(screen.queryByText(/high-materiality/)).not.toBeInTheDocument();
    expect(screen.queryByText("Fragile factor:")).not.toBeInTheDocument();
  });

  it("expands to reveal the detailed explanation, fragile citation, and fast-path provenance note", async () => {
    const user = userEvent.setup();
    renderPillars();

    await user.click(screen.getByRole("button", { name: "Details" }));

    expect(screen.getByText(/high-materiality/)).toBeInTheDocument();
    expect(screen.getByText("Fragile factor:")).toBeInTheDocument();
    expect(screen.getByText(/Fast-path estimate/)).toBeInTheDocument();
  });
});
