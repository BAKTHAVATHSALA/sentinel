import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoCaseQueuePage } from "./DemoCaseQueuePage";
import * as demoApi from "../lib/demoApi";
import type { QueueCaseSummary } from "../lib/types";

function mockDemoRow(overrides: Partial<QueueCaseSummary> = {}): QueueCaseSummary {
  return {
    case_id: "demo_test_case_01",
    transaction_id: "tx_demo_01",
    state: "HUMAN_REVIEW",
    created_at: "2026-09-21T00:00:00Z",
    updated_at: "2026-09-21T00:00:00Z",
    amount: "1499.00",
    currency: "USD",
    merchant_id: "merch_spike",
    risk_band: "HIGH",
    anomaly_tags: ["NEW_DEVICE", "MERCHANT_RISK"],
    robustness_classification: "ROBUST",
    robustness_fragile_factor_id: null,
    final_disposition: null,
    is_escalated_by_me: false,
    ...overrides,
  };
}

describe("DemoCaseQueuePage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders demo navbar, title, and queue rows without requiring auth", async () => {
    vi.spyOn(demoApi, "fetchDemoDashboardCases").mockResolvedValue([
      mockDemoRow({ case_id: "demo_test_case_01", risk_band: "HIGH" }),
      mockDemoRow({ case_id: "demo_test_case_02", amount: "450.00", risk_band: "MEDIUM" }),
    ]);

    render(
      <MemoryRouter>
        <DemoCaseQueuePage />
      </MemoryRouter>
    );

    expect(screen.getByText("Loading demo queue...")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Sentinel Demo Queue")).toBeInTheDocument();
      expect(screen.getByText("DEMO MODE")).toBeInTheDocument();
      expect(screen.getByText("Demo Analyst")).toBeInTheDocument();
      expect(screen.getByText("Reset Demo")).toBeInTheDocument();
      expect(screen.getAllByText("merch_spike").length).toBeGreaterThan(0);
    });
  });

  it("shows empty state when all cases are finalized and offers reset guidance", async () => {
    vi.spyOn(demoApi, "fetchDemoDashboardCases").mockResolvedValue([
      mockDemoRow({ case_id: "demo_test_case_09", state: "FINALIZED", final_disposition: "CLEAR" }),
    ]);

    render(
      <MemoryRouter>
        <DemoCaseQueuePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/All demo cases in this session have been decided/)).toBeInTheDocument();
    });
  });
});
