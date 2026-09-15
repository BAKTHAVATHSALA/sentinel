import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HumanDecisionPanel } from "./HumanDecisionPanel";
import { flaggedFragileCase } from "../test/fixtures";
import * as api from "../lib/api";

describe("HumanDecisionPanel", () => {
  it("keeps every action disabled until the evidence-acknowledged checkbox is checked", async () => {
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={flaggedFragileCase} onDecided={() => {}} />);

    expect(screen.getByRole("button", { name: "Clear" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Block & hold" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Escalate to senior" })).toBeDisabled();

    await user.click(screen.getByText("I have reviewed the evidence above"));

    expect(screen.getByRole("button", { name: "Clear" })).toBeEnabled();
  });

  it("requires a reason before Block & Hold can be confirmed", async () => {
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={flaggedFragileCase} onDecided={() => {}} />);
    await user.click(screen.getByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Block & hold" }));

    const confirmButton = screen.getByRole("button", { name: /confirm block & hold/i });
    expect(confirmButton).toBeDisabled();

    await user.type(screen.getByLabelText(/Analyst ID/), "analyst_42");
    expect(confirmButton).toBeDisabled(); // reason still empty

    await user.type(screen.getByLabelText(/Reason/), "Confirmed fraud pattern");
    expect(confirmButton).toBeEnabled();
  });

  it("does not require a reason for Clear", async () => {
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={flaggedFragileCase} onDecided={() => {}} />);
    await user.click(screen.getByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Clear" }));
    await user.type(screen.getByLabelText(/Analyst ID/), "analyst_42");

    expect(screen.getByRole("button", { name: /confirm clear/i })).toBeEnabled();
  });

  it("submits the exact HumanDecisionRequest shape to the real decision endpoint", async () => {
    const submitSpy = vi.spyOn(api, "submitDecision").mockResolvedValue({
      case_id: flaggedFragileCase.case_id,
      state: "FINALIZED",
      final_disposition: "CLEAR",
      decided_at: "2026-09-15T15:00:00Z",
      idempotent_replay: false,
    });
    const onDecided = vi.fn();
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={flaggedFragileCase} onDecided={onDecided} />);

    await user.click(screen.getByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Clear" }));
    await user.type(screen.getByLabelText(/Analyst ID/), "analyst_42");
    await user.click(screen.getByRole("button", { name: /confirm clear/i }));

    await waitFor(() => expect(onDecided).toHaveBeenCalled());
    expect(submitSpy).toHaveBeenCalledWith(
      flaggedFragileCase.case_id,
      expect.objectContaining({
        case_id: flaggedFragileCase.case_id,
        analyst_id: "analyst_42",
        action: "CLEAR",
        evidence_acknowledged: true,
      }),
    );
  });
});
