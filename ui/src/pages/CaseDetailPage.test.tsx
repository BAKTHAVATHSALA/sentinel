import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, afterEach } from "vitest";
import { CaseDetailPage } from "./CaseDetailPage";
import { cleanCase, flaggedFragileCase } from "../test/fixtures";
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

  it("HUMAN_REVIEW case never displays AUTO_RESOLVED copy", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockResolvedValue(flaggedFragileCase);

    renderCasePage();

    await waitFor(() => expect(screen.getAllByText("HUMAN REVIEW").length).toBeGreaterThan(0));
    expect(screen.queryByText(/resolved automatically/)).not.toBeInTheDocument();
    expect(screen.queryByText("AUTO-RESOLVED")).not.toBeInTheDocument();
    expect(screen.queryByText("No human action required")).not.toBeInTheDocument();
  });

  it("AUTO_RESOLVED case never displays analyst decision controls", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockResolvedValue(cleanCase);

    renderCasePage(cleanCase.case_id);

    await waitFor(() => expect(screen.getAllByText(/resolved automatically/).length).toBeGreaterThan(0));
    // "Human decision" itself is also a PipelineStrip stage label shown for
    // every case regardless of state -- what must be absent is the actual
    // decision panel's controls (final authority header + checkbox + buttons).
    expect(screen.queryByText(/Final authority/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /clear|block|escalate/i })).not.toBeInTheDocument();
    expect(screen.queryByText("I have reviewed the evidence above")).not.toBeInTheDocument();
  });

  it("renders the Investigation Pipeline immediately after the Case Header, before Investigation Summary/Evidence", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockResolvedValue(flaggedFragileCase);

    renderCasePage();

    await waitFor(() => expect(screen.getByText("Investigation summary")).toBeInTheDocument());

    const bodyText = document.body.textContent ?? "";
    const caseIdIndex = bodyText.indexOf(flaggedFragileCase.case_id);
    const pipelineIndex = bodyText.indexOf("Detection");
    const summaryIndex = bodyText.indexOf("Investigation summary");
    // "Evidence" also names a pipeline stage label (appearing before the
    // summary) -- search for the Evidence *section* heading specifically,
    // i.e. the first "Evidence" occurrence after the summary.
    const evidenceIndex = bodyText.indexOf("Evidence", summaryIndex);

    expect(caseIdIndex).toBeGreaterThan(-1);
    expect(pipelineIndex).toBeGreaterThan(caseIdIndex);
    expect(summaryIndex).toBeGreaterThan(pipelineIndex);
    expect(evidenceIndex).toBeGreaterThan(summaryIndex);
  });

  it("keeps every real pipeline stage status visible (Detection/Evidence/Reasoning/Robustness/Policy/Human decision)", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockResolvedValue(flaggedFragileCase);

    renderCasePage();

    await waitFor(() => expect(screen.getByText("Detection")).toBeInTheDocument());
    expect(screen.getByText("Medium risk")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Success")).toBeInTheDocument();
    expect(screen.getAllByText("Fragile").length).toBeGreaterThan(0); // pipeline stage + SupportPillars badge
    expect(screen.getByText("Escalate")).toBeInTheDocument();
    expect(screen.getByText("Awaiting")).toBeInTheDocument();
  });

  it("uses content-driven height (no h-screen/overflow-y-auto forcing the content region to exactly one viewport)", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockResolvedValue(flaggedFragileCase);

    renderCasePage();

    await waitFor(() => expect(screen.getByText("Investigation summary")).toBeInTheDocument());

    // The old layout wrapped everything in a `h-screen` flex column with a
    // `flex-1 overflow-y-auto` content box -- exactly the combination that
    // forced a fixed-viewport-height scroll region (the reported bottom
    // whitespace + double-scrollbar bug). Neither should appear anywhere in
    // the rendered main content tree any more.
    const html = document.body.innerHTML;
    expect(html).not.toContain("h-screen");
    expect(html).not.toContain("overflow-y-auto");
  });

  it("keeps the nav bar pinned via sticky positioning instead of the old fixed-height scroll trick", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockResolvedValue(flaggedFragileCase);

    renderCasePage();

    await waitFor(() => expect(screen.getByText("SENTINEL")).toBeInTheDocument());
    const navBar = screen.getByText("SENTINEL").closest("div.sticky");
    expect(navBar).not.toBeNull();
  });

  it("uses the full available width (no max-width cap) with comfortable side padding, not a narrow document column", async () => {
    mockAuth();
    vi.spyOn(api, "fetchCase").mockResolvedValue(flaggedFragileCase);

    renderCasePage();

    await waitFor(() => expect(screen.getByText("Investigation summary")).toBeInTheDocument());
    expect(document.body.innerHTML).not.toMatch(/max-w-\[\d+px\]/);
  });
});
