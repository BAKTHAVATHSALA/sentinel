import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CaseQueuePage } from "./CaseQueuePage";
import * as api from "../lib/api";
import * as authModule from "../lib/auth";
import { clearAnalystIdentity } from "../lib/analystIdentity";
import type { QueueCaseSummary } from "../lib/types";

function mockAuth() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { uid: "uid_analyst_1", email: "priya@sentinel.demo" } as unknown as ReturnType<typeof authModule.useAuth>["user"],
    loading: false,
    signIn: vi.fn(),
    signOut: vi.fn(),
  });
}

function row(overrides: Partial<QueueCaseSummary> = {}): QueueCaseSummary {
  return {
    case_id: "case_1",
    transaction_id: "tx_1",
    state: "HUMAN_REVIEW",
    created_at: "2026-09-21T00:00:00Z",
    updated_at: "2026-09-21T00:00:00Z",
    amount: "100.00",
    currency: "USD",
    merchant_id: "merch_1",
    risk_band: "LOW",
    anomaly_tags: [],
    robustness_classification: null,
    robustness_fragile_factor_id: null,
    final_disposition: null,
    is_escalated_by_me: false,
    ...overrides,
  };
}

/** Simulates the real backend behavior of api.ts's request(): reading the
 * caller's role off response headers into the shared analystIdentity store,
 * exactly as GET /cases's X-Analyst-Role header does. */
function mockDashboardCases(cases: QueueCaseSummary[], role: "ANALYST" | "SENIOR_ANALYST" = "ANALYST") {
  return vi.spyOn(api, "fetchDashboardCases").mockImplementation(async () => {
    const { setAnalystIdentity } = await import("../lib/analystIdentity");
    setAnalystIdentity({ displayName: role === "ANALYST" ? "Priya Nair" : "Elena Cho", role });
    return cases;
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <CaseQueuePage />
    </MemoryRouter>,
  );
}

describe("CaseQueuePage -- dashboard metrics", () => {
  afterEach(() => {
    clearAnalystIdentity();
  });

  it("shows a loading state before any metric or count renders", async () => {
    mockAuth();
    let resolveFetch: (cases: QueueCaseSummary[]) => void = () => {};
    vi.spyOn(api, "fetchDashboardCases").mockImplementation(
      () => new Promise((resolve) => (resolveFetch = resolve)),
    );
    renderPage();

    expect(screen.getByText("Loading queue...")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-metric-Total Cases")).not.toBeInTheDocument();

    resolveFetch([]);
    await waitFor(() => expect(screen.queryByText("Loading queue...")).not.toBeInTheDocument());
  });

  it("ANALYST: shows Total/Open/Closed/Block & Hold/Escalated to Senior computed from the real fetched cases", async () => {
    mockAuth();
    mockDashboardCases([
      row({ case_id: "open_1", state: "HUMAN_REVIEW" }),
      row({ case_id: "open_2", state: "HUMAN_REVIEW" }),
      row({ case_id: "closed_1", state: "FINALIZED", final_disposition: "CLEAR" }),
      row({ case_id: "closed_blocked", state: "FINALIZED", final_disposition: "BLOCK_HOLD" }),
      row({ case_id: "escalated_1", state: "HUMAN_REVIEW", is_escalated_by_me: true }),
    ]);
    renderPage();

    await waitFor(() => expect(screen.getByTestId("dashboard-metric-Total Cases")).toBeInTheDocument());
    expect(screen.getByTestId("dashboard-metric-Total Cases")).toHaveTextContent("4"); // 2 open + 2 closed; the escalated case is excluded
    expect(screen.getByTestId("dashboard-metric-Open Cases")).toHaveTextContent("2");
    expect(screen.getByTestId("dashboard-metric-Closed Cases")).toHaveTextContent("2");
    expect(screen.getByTestId("dashboard-metric-Block & Hold")).toHaveTextContent("1");
    expect(screen.getByTestId("dashboard-metric-Escalated to Senior")).toHaveTextContent("1");
  });

  it("ANALYST: the queue table only ever shows open, non-escalated cases -- unchanged existing behavior", async () => {
    mockAuth();
    mockDashboardCases([
      row({ case_id: "open_1", state: "HUMAN_REVIEW" }),
      row({ case_id: "closed_1", state: "FINALIZED", final_disposition: "CLEAR" }),
      row({ case_id: "escalated_1", state: "HUMAN_REVIEW", is_escalated_by_me: true }),
    ]);
    renderPage();

    await waitFor(() => expect(screen.getByText("1 open")).toBeInTheDocument());
  });

  it("SENIOR_ANALYST: never shows the Escalated to Senior card", async () => {
    mockAuth();
    mockDashboardCases(
      [row({ case_id: "open_1", state: "HUMAN_REVIEW" })],
      "SENIOR_ANALYST",
    );
    renderPage();

    await waitFor(() => expect(screen.getByTestId("dashboard-metric-Total Cases")).toBeInTheDocument());
    expect(screen.queryByTestId("dashboard-metric-Escalated to Senior")).not.toBeInTheDocument();
    expect(screen.queryByText("Escalated to Senior")).not.toBeInTheDocument();
  });

  it("shows zero-count metrics (0, not '--') for an analyst with no cases at all", async () => {
    mockAuth();
    mockDashboardCases([]);
    renderPage();

    await waitFor(() => expect(screen.getByTestId("dashboard-metric-Total Cases")).toBeInTheDocument());
    expect(screen.getByTestId("dashboard-metric-Total Cases")).toHaveTextContent("0");
    expect(screen.getByTestId("dashboard-metric-Open Cases")).toHaveTextContent("0");
    expect(screen.getByTestId("dashboard-metric-Closed Cases")).toHaveTextContent("0");
    expect(screen.getByTestId("dashboard-metric-Block & Hold")).toHaveTextContent("0");
    expect(screen.getByTestId("dashboard-metric-Escalated to Senior")).toHaveTextContent("0");
    expect(screen.getByText("No cases require review right now.")).toBeInTheDocument();
  });

  it("shows an API failure state and no metric cards when the fetch fails", async () => {
    mockAuth();
    vi.spyOn(api, "fetchDashboardCases").mockRejectedValue(new api.ApiError(500, "Could not load the queue."));
    renderPage();

    await waitFor(() => expect(screen.getByText("Could not load the queue.")).toBeInTheDocument());
    expect(screen.queryByTestId("dashboard-metric-Total Cases")).not.toBeInTheDocument();
  });
});
