import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import * as authModule from "./lib/auth";

/**
 * Routing/auth contract test for the bug reported live: /investigate was
 * redirecting to /login for a logged-out browser because its route element
 * was wrapped in RequireAuth. This test exercises App's actual route tree
 * (not a hand-built stand-in) with a genuinely logged-out auth state, the
 * same shape a real signed-out Firebase session produces (user: null,
 * loading: false) -- so a regression here would fail exactly the way the
 * live bug did.
 */
function mockLoggedOut() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: null,
    loading: false,
    signIn: vi.fn(),
    signOut: vi.fn(),
  });
}

function renderAppAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("App routing while logged out", () => {
  it("/investigate loads the public Transaction Console without redirecting to /login", async () => {
    mockLoggedOut();
    renderAppAt("/investigate");

    expect(await screen.findByText("Transaction Investigation Console")).toBeInTheDocument();
    expect(screen.queryByText("Sign in to review cases.")).not.toBeInTheDocument();
  });

  it("/ redirects to /login (Analyst Portal stays protected)", async () => {
    mockLoggedOut();
    renderAppAt("/");

    expect(await screen.findByText("Sign in to review cases.")).toBeInTheDocument();
  });

  it("/case/:caseId redirects to /login (Analyst Portal stays protected)", async () => {
    mockLoggedOut();
    renderAppAt("/case/case_e41fc15a8461");

    expect(await screen.findByText("Sign in to review cases.")).toBeInTheDocument();
  });
});
