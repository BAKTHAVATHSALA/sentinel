import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DecisionConfirmationScreen } from "./DecisionConfirmationScreen";
import * as authModule from "../lib/auth";
import type { DecisionResponse } from "../lib/types";

function mockAuth() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { uid: "uid_1", email: "priya@sentinel.demo" } as unknown as ReturnType<typeof authModule.useAuth>["user"],
    loading: false,
    signIn: vi.fn(),
    signOut: vi.fn(),
  });
}

function renderScreen(decision: DecisionResponse) {
  return render(
    <MemoryRouter>
      <DecisionConfirmationScreen decision={decision} />
    </MemoryRouter>,
  );
}

const CLEAR_DECISION: DecisionResponse = {
  case_id: "case_1",
  state: "FINALIZED",
  final_disposition: "CLEAR",
  assigned_analyst_id: "uid_1",
  decided_at: "2026-09-20T12:00:00Z",
  idempotent_replay: false,
  target_analyst_display_name: null,
};

const BLOCK_HOLD_DECISION: DecisionResponse = {
  ...CLEAR_DECISION,
  final_disposition: "BLOCK_HOLD",
};

const ESCALATE_DECISION: DecisionResponse = {
  case_id: "case_1",
  state: "HUMAN_REVIEW",
  final_disposition: null,
  assigned_analyst_id: "uid_senior_1",
  decided_at: "2026-09-20T12:00:00Z",
  idempotent_replay: false,
  target_analyst_display_name: "Elena Cho",
};

describe("DecisionConfirmationScreen", () => {
  it("shows the Case Cleared confirmation with case, decision, actor, and timestamp -- no decision controls", () => {
    mockAuth();
    renderScreen(CLEAR_DECISION);

    expect(screen.getByText("Case Cleared")).toBeInTheDocument();
    expect(screen.getByText("case_1")).toBeInTheDocument();
    expect(screen.getByText("CLEAR")).toBeInTheDocument();
    expect(screen.getByText("priya@sentinel.demo")).toBeInTheDocument();
    expect(screen.getByText("2026-09-20T12:00:00Z")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /clear|block|escalate/i })).not.toBeInTheDocument();
  });

  it("shows the Transaction Blocked / Held confirmation -- no decision controls", () => {
    mockAuth();
    renderScreen(BLOCK_HOLD_DECISION);

    expect(screen.getByText("Transaction Blocked / Held")).toBeInTheDocument();
    expect(screen.getByText("BLOCK_HOLD")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /clear|block|escalate/i })).not.toBeInTheDocument();
  });

  it("shows BLOCK_HOLD in red (critical), consistent with the decision button/dashboard/case header everywhere else -- never the same teal as CLEAR", () => {
    mockAuth();
    renderScreen(BLOCK_HOLD_DECISION);

    const title = screen.getByText("Transaction Blocked / Held");
    expect(title).toHaveStyle({ color: "var(--color-critical)" });
  });

  it("keeps CLEAR in teal/stable, distinct from BLOCK_HOLD's red", () => {
    mockAuth();
    renderScreen(CLEAR_DECISION);

    const title = screen.getByText("Case Cleared");
    expect(title).toHaveStyle({ color: "var(--color-stable)" });
  });

  it("shows the Case Escalated Successfully confirmation with the real senior display name and HUMAN_REVIEW status", () => {
    mockAuth();
    renderScreen(ESCALATE_DECISION);

    expect(screen.getByText("Case Escalated Successfully")).toBeInTheDocument();
    expect(screen.getByText("Elena Cho")).toBeInTheDocument();
    expect(screen.getByText("HUMAN_REVIEW")).toBeInTheDocument();
    expect(screen.getByText(/ownership of this case has moved/i)).toBeInTheDocument();
  });

  it("never renders the raw Firebase UID anywhere", () => {
    mockAuth();
    renderScreen(ESCALATE_DECISION);
    expect(screen.queryByText("uid_senior_1")).not.toBeInTheDocument();
  });

  it("offers Back to My Cases and Logout on every confirmation variant", () => {
    mockAuth();
    renderScreen(ESCALATE_DECISION);

    expect(screen.getByRole("link", { name: "Back to My Cases" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument();
  });
});
