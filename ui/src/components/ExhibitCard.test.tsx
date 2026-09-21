import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ExhibitCard } from "./ExhibitCard";
import { CitationThreadProvider } from "./CitationThread";
import type { Fact } from "../lib/types";

const DEVICE_FACT: Fact = {
  fact_id: "fact_01_device_history",
  type: "device_history",
  subject_id: "cust_1",
  value: { known_device: false, transaction_count: 3 },
  source_tool: "get_device_history",
  source_record_id: "rec_device_001",
  observed_at: "2026-09-15T14:56:10Z",
  retrieved_at: "2026-09-15T14:56:12Z",
  quality: "DERIVED",
};

function renderExhibit(fact: Fact = DEVICE_FACT, index = 0, excluded = false) {
  return render(
    <CitationThreadProvider>
      <ExhibitCard fact={fact} index={index} excluded={excluded} />
    </CitationThreadProvider>,
  );
}

describe("ExhibitCard", () => {
  it("is collapsed by default: shows exhibit number, tool, quality, and a concise conclusion, not the raw fields", () => {
    renderExhibit();
    expect(screen.getByText("Exhibit 01")).toBeInTheDocument();
    expect(screen.getByText("Device history")).toBeInTheDocument();
    expect(screen.getByText("DERIVED")).toBeInTheDocument();
    expect(screen.getByText("New device confirmed")).toBeInTheDocument();
    expect(screen.queryByText("known device")).not.toBeInTheDocument();
    expect(screen.queryByText("source record id")).not.toBeInTheDocument();
  });

  it("expands to reveal the complete existing evidence: every field, source_record_id, both timestamps", async () => {
    const user = userEvent.setup();
    renderExhibit();

    await user.click(screen.getByRole("button", { name: "View evidence" }));

    expect(screen.getByText("known device")).toBeInTheDocument();
    expect(screen.getByText("false")).toBeInTheDocument();
    expect(screen.getByText("transaction count")).toBeInTheDocument();
    expect(screen.getByText("source record id")).toBeInTheDocument();
    expect(screen.getByText("rec_device_001")).toBeInTheDocument();
    expect(screen.getByText("observed at")).toBeInTheDocument();
    expect(screen.getByText("retrieved at")).toBeInTheDocument();
  });

  it("collapses back on toggle, hiding the detailed fields again without losing them permanently", async () => {
    const user = userEvent.setup();
    renderExhibit();

    await user.click(screen.getByRole("button", { name: "View evidence" }));
    expect(screen.getByText("source record id")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Hide evidence" }));
    expect(screen.queryByText("source record id")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "View evidence" }));
    expect(screen.getByText("source record id")).toBeInTheDocument();
  });

  it("falls back to the tool title when no safe conclusion can be derived (unrecognized tool)", () => {
    renderExhibit({ ...DEVICE_FACT, source_tool: "some_future_tool", value: { anything: 1 } });
    expect(screen.getAllByText("some_future_tool").length).toBe(2); // header label + fallback conclusion
  });

  it("marks an excluded fact (removed for a counterfactual re-check) visibly", () => {
    renderExhibit(DEVICE_FACT, 0, true);
    expect(screen.getByText("Excluded from this re-check")).toBeInTheDocument();
  });
});
