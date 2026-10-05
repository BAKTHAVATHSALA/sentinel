import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HumanDecisionPanel } from "./HumanDecisionPanel";
import { flaggedFragileCase } from "../test/fixtures";
import * as api from "../lib/api";
import * as authModule from "../lib/auth";

const FAKE_USER = { uid: "uid_test_analyst" } as unknown as ReturnType<typeof authModule.useAuth>["user"];

function mockAuth() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: FAKE_USER,
    loading: false,
    signIn: vi.fn(),
    signOut: vi.fn(),
  });
}

const caseWithSeniorAvailable = {
  ...flaggedFragileCase,
  available_seniors: [{ uid: "uid_senior_1", display_name: "Elena Cho", email: "senior1@sentinel.demo" }],
};

describe("HumanDecisionPanel", () => {
  it("keeps every action disabled until the evidence-acknowledged checkbox is checked", async () => {
    mockAuth();
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={caseWithSeniorAvailable} onDecided={() => {}} />);

    expect(screen.getByRole("button", { name: "Clear" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Block & hold" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Escalate to senior" })).toBeDisabled();

    await user.click(screen.getByText("I have reviewed the evidence above"));

    expect(screen.getByRole("button", { name: "Clear" })).toBeEnabled();
  });

  it("does not offer Escalate to senior when available_seniors is absent (senior caller)", async () => {
    mockAuth();
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={flaggedFragileCase} onDecided={() => {}} />);
    await user.click(screen.getByText("I have reviewed the evidence above"));

    expect(screen.queryByRole("button", { name: "Escalate to senior" })).not.toBeInTheDocument();
  });

  it("requires a reason before Block & Hold can be confirmed", async () => {
    mockAuth();
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={caseWithSeniorAvailable} onDecided={() => {}} />);
    await user.click(screen.getByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Block & hold" }));

    const confirmButton = screen.getByRole("button", { name: /confirm block & hold/i });
    expect(confirmButton).toBeDisabled();

    await user.type(screen.getByLabelText(/Reason/), "Confirmed fraud pattern");
    expect(confirmButton).toBeEnabled();
  });

  it("requires a reason for Clear too (mandatory for all three actions)", async () => {
    mockAuth();
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={caseWithSeniorAvailable} onDecided={() => {}} />);
    await user.click(screen.getByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.getByRole("button", { name: /confirm clear/i })).toBeDisabled();

    await user.type(screen.getByLabelText(/Reason/), "Reviewed, legitimate purchase");
    expect(screen.getByRole("button", { name: /confirm clear/i })).toBeEnabled();
  });

  it("requires selecting a senior before Escalate to senior can be confirmed", async () => {
    mockAuth();
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={caseWithSeniorAvailable} onDecided={() => {}} />);
    await user.click(screen.getByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Escalate to senior" }));
    await user.type(screen.getByLabelText(/Reason/), "Needs a second opinion");

    const confirmButton = screen.getByRole("button", { name: /confirm escalate to senior/i });
    expect(confirmButton).toBeDisabled();

    await user.selectOptions(screen.getByLabelText(/Escalate to/), "uid_senior_1");
    expect(confirmButton).toBeEnabled();
    // Only the senior's display name is shown -- never their email or raw UID.
    expect(screen.getByText("Elena Cho")).toBeInTheDocument();
    expect(screen.queryByText(/senior1@sentinel\.demo/)).not.toBeInTheDocument();
    expect(screen.queryByText("uid_senior_1")).not.toBeInTheDocument();
  });

  it("submits the exact HumanDecisionRequest shape, deriving analyst_id from the authenticated caller", async () => {
    mockAuth();
    const submitSpy = vi.spyOn(api, "submitDecision").mockResolvedValue({
      case_id: flaggedFragileCase.case_id,
      state: "FINALIZED",
      final_disposition: "CLEAR",
      assigned_analyst_id: "uid_test_analyst",
      decided_at: "2026-09-15T15:00:00Z",
      idempotent_replay: false,
      target_analyst_display_name: null,
    });
    const onDecided = vi.fn();
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={caseWithSeniorAvailable} onDecided={onDecided} />);

    await user.click(screen.getByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Clear" }));
    await user.type(screen.getByLabelText(/Reason/), "Reviewed, legitimate purchase");
    await user.click(screen.getByRole("button", { name: /confirm clear/i }));

    await waitFor(() => expect(onDecided).toHaveBeenCalled());
    expect(submitSpy).toHaveBeenCalledWith(
      flaggedFragileCase.case_id,
      expect.objectContaining({
        case_id: flaggedFragileCase.case_id,
        analyst_id: "uid_test_analyst",
        action: "CLEAR",
        reason: "Reviewed, legitimate purchase",
        evidence_acknowledged: true,
      }),
    );
  });

  it("submits target_analyst_id for an escalation", async () => {
    mockAuth();
    const submitSpy = vi.spyOn(api, "submitDecision").mockResolvedValue({
      case_id: flaggedFragileCase.case_id,
      state: "HUMAN_REVIEW",
      final_disposition: null,
      assigned_analyst_id: "uid_senior_1",
      decided_at: "2026-09-15T15:00:00Z",
      idempotent_replay: false,
      target_analyst_display_name: "Elena Cho",
    });
    const user = userEvent.setup();
    render(<HumanDecisionPanel caseDoc={caseWithSeniorAvailable} onDecided={() => {}} />);

    await user.click(screen.getByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Escalate to senior" }));
    await user.type(screen.getByLabelText(/Reason/), "Needs a second opinion");
    await user.selectOptions(screen.getByLabelText(/Escalate to/), "uid_senior_1");
    await user.click(screen.getByRole("button", { name: /confirm escalate to senior/i }));

    await waitFor(() => expect(submitSpy).toHaveBeenCalled());
    expect(submitSpy).toHaveBeenCalledWith(
      flaggedFragileCase.case_id,
      expect.objectContaining({ action: "ESCALATE_SENIOR", target_analyst_id: "uid_senior_1" }),
    );
  });
});
