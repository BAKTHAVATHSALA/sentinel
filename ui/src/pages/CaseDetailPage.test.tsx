import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, afterEach } from "vitest";
import { CaseDetailPage } from "./CaseDetailPage";
import { flaggedFragileCase } from "../test/fixtures";
import * as api from "../lib/api";
import * as authModule from "../lib/auth";
import { clearAnalystIdentity } from "../lib/analystIdentity";

const FAKE_USER = { uid: "uid_test_analyst", email: "priya@sentinel.demo" } as unknown as ReturnType<
  typeof authModule.useAuth
>["user"];

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

function renderCasePage(caseId = flaggedFragileCase.case_id) {
  return render(
    <MemoryRouter initialEntries={[`/cases/${caseId}`]}>
      <Routes>
        <Route path="/cases/:caseId" element={<CaseDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CaseDetailPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    clearAnalystIdentity();
  });

  it("renders the persistent nav bar alongside case content", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockResolvedValue(flaggedFragileCase);

    renderCasePage();

    await waitFor(() => expect(screen.getByText("SENTINEL")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "My Cases" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument();
  });

  it("CRITICAL: after a successful ESCALATE_SENIOR decision, never calls fetchCase again", async () => {
    mockAuth();
    const fetchCaseSpy = vi.spyOn(api, "fetchCase").mockResolvedValue(caseWithSeniorAvailable);
    vi.spyOn(api, "submitDecision").mockResolvedValue({
      case_id: caseWithSeniorAvailable.case_id,
      state: "HUMAN_REVIEW",
      final_disposition: null,
      assigned_analyst_id: "uid_senior_1",
      decided_at: "2026-09-20T12:00:00Z",
      idempotent_replay: false,
      target_analyst_display_name: "Elena Cho",
    });

    const user = userEvent.setup();
    renderCasePage(caseWithSeniorAvailable.case_id);

    await user.click(await screen.findByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Escalate to senior" }));
    await user.type(screen.getByLabelText(/Reason/), "Needs a second opinion");
    await user.selectOptions(screen.getByLabelText(/Escalate to/), "uid_senior_1");
    await user.click(screen.getByRole("button", { name: /confirm escalate to senior/i }));

    await waitFor(() => expect(screen.getByText("Case Escalated Successfully")).toBeInTheDocument());

    expect(fetchCaseSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Elena Cho")).toBeInTheDocument();
    // The confirmation screen renders no decision controls of its own.
    expect(screen.queryByRole("button", { name: /confirm|clear|block|escalate/i })).not.toBeInTheDocument();
    // Persistent nav is still present on the confirmation screen.
    expect(screen.getByText("SENTINEL")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to My Cases" })).toBeInTheDocument();
  });

  it("after a successful CLEAR decision, shows the Case Cleared confirmation and does not refetch", async () => {
    mockAuth();
    const fetchCaseSpy = vi.spyOn(api, "fetchCase").mockResolvedValue(flaggedFragileCase);
    vi.spyOn(api, "submitDecision").mockResolvedValue({
      case_id: flaggedFragileCase.case_id,
      state: "FINALIZED",
      final_disposition: "CLEAR",
      assigned_analyst_id: "uid_test_analyst",
      decided_at: "2026-09-20T12:00:00Z",
      idempotent_replay: false,
      target_analyst_display_name: null,
    });

    const user = userEvent.setup();
    renderCasePage();

    await user.click(await screen.findByText("I have reviewed the evidence above"));
    await user.click(screen.getByRole("button", { name: "Clear" }));
    await user.type(screen.getByLabelText(/Reason/), "Reviewed, legitimate purchase");
    await user.click(screen.getByRole("button", { name: /confirm clear/i }));

    await waitFor(() => expect(screen.getByText("Case Cleared")).toBeInTheDocument());

    expect(fetchCaseSpy).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: /clear|block|escalate/i })).not.toBeInTheDocument();
  });

  it("shows the generic unauthorized/not-found screen (Back to My Cases + Logout, no Retry) on a 404", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockRejectedValue(new api.ApiError(404, "This case is not available."));

    renderCasePage("case_no_longer_owned");

    await waitFor(() => expect(screen.getByText("This case is not available.")).toBeInTheDocument());

    expect(screen.getByText("SENTINEL")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to My Cases" })).toHaveAttribute("href", "/");
    expect(screen.getAllByRole("button", { name: "Logout" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });
});
