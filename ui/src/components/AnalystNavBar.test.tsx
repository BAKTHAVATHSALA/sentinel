import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalystNavBar } from "./AnalystNavBar";
import * as authModule from "../lib/auth";
import { clearAnalystIdentity, setAnalystIdentity } from "../lib/analystIdentity";

function mockAuth(signOut = vi.fn()) {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { uid: "uid_1", email: "priya@sentinel.demo" } as unknown as ReturnType<typeof authModule.useAuth>["user"],
    loading: false,
    signIn: vi.fn(),
    signOut,
  });
}

function renderNavBar() {
  return render(
    <MemoryRouter>
      <AnalystNavBar />
    </MemoryRouter>,
  );
}

describe("AnalystNavBar", () => {
  afterEach(() => {
    clearAnalystIdentity();
  });

  it("always shows the Sentinel wordmark, My Cases link, and Logout button", () => {
    mockAuth();
    renderNavBar();

    expect(screen.getByText("SENTINEL")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My Cases" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument();
  });

  it("shows the caller's real server-resolved display name and role once identity is available", () => {
    mockAuth();
    setAnalystIdentity({ displayName: "Priya Nair", role: "ANALYST" });
    renderNavBar();

    expect(screen.getByText("Priya Nair")).toBeInTheDocument();
    expect(screen.getByText("Analyst")).toBeInTheDocument();
  });

  it("shows a friendly label for SENIOR_ANALYST", () => {
    mockAuth();
    setAnalystIdentity({ displayName: "Elena Cho", role: "SENIOR_ANALYST" });
    renderNavBar();

    expect(screen.getByText("Elena Cho")).toBeInTheDocument();
    expect(screen.getByText("Senior Analyst")).toBeInTheDocument();
  });

  it("does not crash and shows no name/role before identity has arrived", () => {
    mockAuth();
    renderNavBar();
    expect(screen.getByText("SENTINEL")).toBeInTheDocument();
  });

  it("logs out via the real auth signOut function", async () => {
    const signOut = vi.fn();
    mockAuth(signOut);
    const user = userEvent.setup();
    renderNavBar();

    await user.click(screen.getByRole("button", { name: "Logout" }));

    expect(signOut).toHaveBeenCalled();
  });
});
