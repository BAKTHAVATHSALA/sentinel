import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CitationThreadProvider } from "./CitationThread";
import { FindingsPanel } from "./FindingsPanel";
import { flaggedFragileCase } from "../test/fixtures";

const exhibitNumbers: Record<string, number> = {};
flaggedFragileCase.evidence_bundle!.facts.forEach((f, i) => (exhibitNumbers[f.fact_id] = i + 1));

function renderPanel() {
  return render(
    <CitationThreadProvider>
      <FindingsPanel findings={flaggedFragileCase.findings!} exhibitNumbers={exhibitNumbers} />
    </CitationThreadProvider>,
  );
}

describe("FindingsPanel", () => {
  it("keeps the 'Gemini's assessment · Advisory, not a decision' header", () => {
    renderPanel();
    expect(screen.getByText("Gemini's assessment")).toBeInTheDocument();
    expect(screen.getByText(/Advisory, not a decision/)).toBeInTheDocument();
  });

  it("shows Supporting/Counter factors and evidence gaps by default", () => {
    renderPanel();
    expect(screen.getByText("Supporting")).toBeInTheDocument();
    expect(screen.getByText("Device shared with another account.")).toBeInTheDocument();
  });

  it("hides the full narrative summary text by default", () => {
    renderPanel();
    expect(
      screen.queryByText("The device was seen on a different account two hours earlier, which is a material risk signal."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show full assessment" })).toBeInTheDocument();
  });

  it("expands to show the exact, unmodified full narrative text on demand", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole("button", { name: "Show full assessment" }));

    expect(
      screen.getByText("The device was seen on a different account two hours earlier, which is a material risk signal."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hide full assessment" })).toBeInTheDocument();
  });
});
