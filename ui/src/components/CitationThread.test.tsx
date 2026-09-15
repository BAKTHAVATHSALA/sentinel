import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CitationThreadProvider } from "./CitationThread";
import { ExhibitCard } from "./ExhibitCard";
import { CitationChip } from "./CitationChip";
import { flaggedFragileCase } from "../test/fixtures";

const fact = flaggedFragileCase.evidence_bundle!.facts[1]; // fact_02_linked_entities

describe("Citation thread (signature interaction)", () => {
  it("highlights the exact exhibit a citation chip points to, on focus", async () => {
    const user = userEvent.setup();
    render(
      <CitationThreadProvider>
        <ExhibitCard fact={fact} index={1} />
        <CitationChip factIds={[fact.fact_id]} exhibitNumbers={{ [fact.fact_id]: 2 }} />
      </CitationThreadProvider>,
    );

    const exhibit = document.getElementById(`exhibit-${fact.fact_id}`)!;
    expect(exhibit.className).not.toContain("border-[var(--color-stable)]");

    await user.tab(); // focuses the citation chip (only focusable element)
    expect(exhibit.className).toContain("border-[var(--color-stable)]");

    await user.tab(); // move focus away -> blur clears the thread
    expect(exhibit.className).not.toContain("border-[var(--color-stable)]");
  });

  it("labels the chip with the real exhibit number, not a fabricated one", () => {
    render(
      <CitationThreadProvider>
        <ExhibitCard fact={fact} index={1} />
        <CitationChip factIds={[fact.fact_id]} exhibitNumbers={{ [fact.fact_id]: 2 }} />
      </CitationThreadProvider>,
    );
    expect(screen.getByRole("button", { name: "Exhibit 02" })).toBeInTheDocument();
  });
});
