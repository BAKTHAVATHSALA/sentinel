import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { CaseUnavailableNotice, EmptyInvestigationNotice } from "./StateNotices";
import * as authModule from "../lib/auth";

function mockAuth(signOut = vi.fn()) {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { uid: "uid_1", email: "priya@sentinel.demo" } as unknown as ReturnType<typeof authModule.useAuth>["user"],
    loading: false,
    signIn: vi.fn(),
    signOut,
  });
}

describe("CaseUnavailableNotice", () => {
  it("shows a generic message plus Back to My Cases and Logout, with no Retry affordance", () => {
    mockAuth();
    render(
      <MemoryRouter>
        <CaseUnavailableNotice message="This case is not available." />
      </MemoryRouter>,
    );

    expect(screen.getByText("This case is not available.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to My Cases" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("logs out via the real auth signOut function", async () => {
    const signOut = vi.fn();
    mockAuth(signOut);
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CaseUnavailableNotice message="This case is not available." />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Logout" }));

    expect(signOut).toHaveBeenCalled();
  });
});

describe("EmptyInvestigationNotice", () => {
  it("says the transaction resolved automatically for an AUTO_RESOLVED case", () => {
    render(<EmptyInvestigationNotice state="AUTO_RESOLVED" />);
    expect(screen.getByText(/resolved automatically/)).toBeInTheDocument();
  });

  it("never claims 'resolved automatically' for a HUMAN_REVIEW case with no evidence bundle -- the CLEAN-but-elevated-risk path", () => {
    render(<EmptyInvestigationNotice state="HUMAN_REVIEW" />);
    expect(screen.queryByText(/resolved automatically/)).not.toBeInTheDocument();
    expect(screen.getByText(/still requires a human decision/)).toBeInTheDocument();
  });
});
