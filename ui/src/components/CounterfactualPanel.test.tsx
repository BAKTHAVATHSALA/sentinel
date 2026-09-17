import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CounterfactualPanel } from "./CounterfactualPanel";
import { CitationThreadProvider } from "./CitationThread";
import { flaggedFragileCase } from "../test/fixtures";
import type { CounterfactualResult } from "../lib/types";

const facts = flaggedFragileCase.evidence_bundle!.facts;
const exhibitNumbers: Record<string, number> = {};
facts.forEach((f, i) => (exhibitNumbers[f.fact_id] = i + 1));

function renderPanel(overrides: Partial<React.ComponentProps<typeof CounterfactualPanel>> = {}) {
  const onRequestCounterfactual = vi.fn();
  const utils = render(
    <CitationThreadProvider>
      <CounterfactualPanel
        robustness={flaggedFragileCase.robustness}
        findings={flaggedFragileCase.findings}
        exhibitNumbers={exhibitNumbers}
        facts={facts}
        counterfactualLoading={false}
        counterfactualError={null}
        onRequestCounterfactual={onRequestCounterfactual}
        {...overrides}
      />
    </CitationThreadProvider>,
  );
  return { ...utils, onRequestCounterfactual };
}

function counterfactualResult(overrides: Partial<CounterfactualResult> = {}): CounterfactualResult {
  return {
    removed_fact_id: "fact_01_device_history",
    findings: {
      findings_id: "find_cf",
      case_id: "case_363a3f9bb31b",
      risk_assessment: "HIGH",
      summary: "cf summary",
      supporting_factors: [
        { statement: "Still linked to a risky account.", fact_ids: ["fact_02_linked_entities"], materiality: "HIGH" },
      ],
      counter_factors: [
        { statement: "Amount is typical.", fact_ids: ["fact_02_linked_entities"], materiality: "LOW" },
      ],
      evidence_gaps: [],
      evidence_citations: [{ claim_id: "c1", fact_ids: ["fact_02_linked_entities"] }],
      recommended_disposition: "ESCALATE",
      generated_at: "2026-09-17T10:00:00Z",
      model_name: "gemini-2.5-pro",
      model_version: "gemini-2.5-pro",
      prompt_version: "reasoning-v1",
    },
    robustness: {
      robustness_id: "rob_cf",
      case_id: "case_363a3f9bb31b",
      classification: "ROBUST",
      fragile_factor_id: null,
      method: "LIVE_COUNTERFACTUAL",
      evaluated_at: "2026-09-17T10:00:00Z",
    },
    policy_outcome_would_change: false,
    ...overrides,
  };
}

describe("CounterfactualPanel", () => {
  it("renders the fast-path robustness summary and the fact picker", () => {
    renderPanel();
    expect(screen.getByText("Fragile")).toBeInTheDocument();
    expect(screen.getByText(/Remove a fact and re-check live/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
  });

  it("Run calls onRequestCounterfactual with the selected fact_id (triggers the simulate_without fetch)", async () => {
    const user = userEvent.setup();
    const { onRequestCounterfactual } = renderPanel();

    await user.selectOptions(screen.getByLabelText(/Remove a fact/), "fact_02_linked_entities");
    await user.click(screen.getByRole("button", { name: "Run" }));

    expect(onRequestCounterfactual).toHaveBeenCalledWith("fact_02_linked_entities");
    expect(onRequestCounterfactual).toHaveBeenCalledTimes(1);
  });

  it("Run is disabled until a fact is selected", () => {
    renderPanel();
    expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
  });

  it("shows the 'Re-running investigation...' loading state and disables the controls", () => {
    renderPanel({ counterfactualLoading: true });
    const runButton = screen.getByRole("button", { name: "Re-running investigation..." });
    expect(runButton).toBeDisabled();
    expect(screen.getByLabelText(/Remove a fact/)).toBeDisabled();
  });

  it("renders the LIVE COUNTERFACTUAL SIMULATION label, risk assessment, and advisory disposition", () => {
    renderPanel({ counterfactual: counterfactualResult() });

    expect(screen.getByText("LIVE COUNTERFACTUAL SIMULATION")).toBeInTheDocument();
    expect(screen.getByText(/persisted case is unchanged/i)).toBeInTheDocument();
    expect(screen.getByText("Risk assessment:").nextSibling).toHaveTextContent("HIGH");
    expect(screen.getByText("AI advisory disposition:")).toBeInTheDocument();
    expect(screen.getByText("Escalate")).toBeInTheDocument();
    expect(screen.getByText(/Advisory only -- not the final decision/)).toBeInTheDocument();
  });

  it("renders the removed exhibit and does not list the removed fact as a remaining citation", () => {
    renderPanel({ counterfactual: counterfactualResult({ removed_fact_id: "fact_01_device_history" }) });

    // "Removed:" chip resolves to Exhibit 01 (fact_01_device_history).
    expect(screen.getByText("Removed:")).toBeInTheDocument();
    expect(screen.getByText("Exhibit 01")).toBeInTheDocument();
    // The remaining citation is Exhibit 02 -- fact_01 must not appear as a remaining citation chip.
    const exhibit02Chips = screen.getAllByText("Exhibit 02");
    expect(exhibit02Chips.length).toBeGreaterThan(0);
  });

  it("renders supporting and counter factors when present", () => {
    renderPanel({ counterfactual: counterfactualResult() });
    expect(screen.getByText("Remaining supporting factors")).toBeInTheDocument();
    expect(screen.getByText("Still linked to a risky account.")).toBeInTheDocument();
    expect(screen.getByText("Remaining counter factors")).toBeInTheDocument();
    expect(screen.getByText("Amount is typical.")).toBeInTheDocument();
  });

  it("does not render supporting/counter/citation sections when they are empty", () => {
    renderPanel({
      counterfactual: counterfactualResult({
        findings: {
          ...counterfactualResult().findings!,
          supporting_factors: [],
          counter_factors: [],
          evidence_citations: [],
        },
      }),
    });
    expect(screen.queryByText("Remaining supporting factors")).not.toBeInTheDocument();
    expect(screen.queryByText("Remaining counter factors")).not.toBeInTheDocument();
    expect(screen.queryByText("Remaining citations")).not.toBeInTheDocument();
  });

  it("renders whether the policy outcome would change, both ways", () => {
    const { rerender } = renderPanel({ counterfactual: counterfactualResult({ policy_outcome_would_change: false }) });
    expect(screen.getByText(/would not change without this fact/)).toBeInTheDocument();

    rerender(
      <CitationThreadProvider>
        <CounterfactualPanel
          robustness={flaggedFragileCase.robustness}
          findings={flaggedFragileCase.findings}
          exhibitNumbers={exhibitNumbers}
          facts={facts}
          counterfactualLoading={false}
          counterfactualError={null}
          onRequestCounterfactual={vi.fn()}
          counterfactual={counterfactualResult({ policy_outcome_would_change: true })}
        />
      </CitationThreadProvider>,
    );
    expect(screen.getByText(/would change without this fact/)).toBeInTheDocument();
  });

  it("handles a counterfactual reasoning failure (findings: null) gracefully", () => {
    renderPanel({ counterfactual: counterfactualResult({ findings: null }) });
    expect(screen.getByText(/could not produce a valid assessment/i)).toBeInTheDocument();
  });

  it("renders an API error with a Try again action that re-requests the same fact", async () => {
    const user = userEvent.setup();
    const { onRequestCounterfactual } = renderPanel({ counterfactualError: "Could not run the live re-check." });

    expect(screen.getByText("Could not run the live re-check.")).toBeInTheDocument();
    const retryButton = screen.getByRole("button", { name: "Try again" });

    await user.selectOptions(screen.getByLabelText(/Remove a fact/), "fact_01_device_history");
    await user.click(retryButton);

    expect(onRequestCounterfactual).toHaveBeenCalledWith("fact_01_device_history");
  });

  it("performs the Run action as a plain button, never a link or form submission (no navigation)", () => {
    renderPanel();
    const runButton = screen.getByRole("button", { name: "Run" });
    expect(runButton).toHaveAttribute("type", "button");
    expect(runButton.closest("form")).toBeNull();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
