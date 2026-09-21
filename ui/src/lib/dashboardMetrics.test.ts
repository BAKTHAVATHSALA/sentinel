import { describe, expect, it } from "vitest";
import { computeDashboardMetrics } from "./dashboardMetrics";
import type { QueueCaseSummary } from "./types";

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

describe("computeDashboardMetrics", () => {
  it("returns all zeros for an empty case list", () => {
    const metrics = computeDashboardMetrics([]);
    expect(metrics).toEqual({
      totalCases: 0,
      openCases: 0,
      closedCases: 0,
      blockHoldCases: 0,
      escalatedToSenior: 0,
    });
  });

  it("counts Total Cases as every row currently assigned to the caller (open + closed), excluding escalated-away cases", () => {
    const cases = [
      row({ case_id: "open_1", state: "HUMAN_REVIEW" }),
      row({ case_id: "closed_1", state: "FINALIZED", final_disposition: "CLEAR" }),
      row({ case_id: "escalated_1", state: "HUMAN_REVIEW", is_escalated_by_me: true }),
    ];
    expect(computeDashboardMetrics(cases).totalCases).toBe(2);
  });

  it("counts Open Cases as HUMAN_REVIEW rows not escalated away", () => {
    const cases = [
      row({ case_id: "open_1", state: "HUMAN_REVIEW" }),
      row({ case_id: "open_2", state: "HUMAN_REVIEW" }),
      row({ case_id: "closed_1", state: "FINALIZED", final_disposition: "CLEAR" }),
      row({ case_id: "escalated_1", state: "HUMAN_REVIEW", is_escalated_by_me: true }),
    ];
    expect(computeDashboardMetrics(cases).openCases).toBe(2);
  });

  it("counts Closed Cases as FINALIZED rows not escalated away", () => {
    const cases = [
      row({ case_id: "closed_1", state: "FINALIZED", final_disposition: "CLEAR" }),
      row({ case_id: "closed_2", state: "FINALIZED", final_disposition: "BLOCK_HOLD" }),
      row({ case_id: "open_1", state: "HUMAN_REVIEW" }),
    ];
    expect(computeDashboardMetrics(cases).closedCases).toBe(2);
  });

  it("counts Block & Hold as only the FINALIZED rows whose final_disposition is BLOCK_HOLD", () => {
    const cases = [
      row({ case_id: "cleared_1", state: "FINALIZED", final_disposition: "CLEAR" }),
      row({ case_id: "blocked_1", state: "FINALIZED", final_disposition: "BLOCK_HOLD" }),
      row({ case_id: "blocked_2", state: "FINALIZED", final_disposition: "BLOCK_HOLD" }),
    ];
    expect(computeDashboardMetrics(cases).blockHoldCases).toBe(2);
  });

  it("never counts an open (non-finalized) case toward Block & Hold even if final_disposition were somehow present", () => {
    const cases = [row({ state: "HUMAN_REVIEW", final_disposition: "BLOCK_HOLD" })];
    expect(computeDashboardMetrics(cases).blockHoldCases).toBe(0);
  });

  it("counts Escalated to Senior as every row with is_escalated_by_me true, regardless of its current state", () => {
    const cases = [
      row({ case_id: "esc_open", state: "HUMAN_REVIEW", is_escalated_by_me: true }),
      row({ case_id: "esc_closed", state: "FINALIZED", final_disposition: "BLOCK_HOLD", is_escalated_by_me: true }),
      row({ case_id: "own_1", state: "HUMAN_REVIEW" }),
    ];
    expect(computeDashboardMetrics(cases).escalatedToSenior).toBe(2);
  });

  it("keeps Total/Open/Closed unaffected by however many cases were escalated", () => {
    const cases = [
      row({ case_id: "esc_1", is_escalated_by_me: true }),
      row({ case_id: "esc_2", is_escalated_by_me: true }),
      row({ case_id: "esc_3", is_escalated_by_me: true }),
    ];
    const metrics = computeDashboardMetrics(cases);
    expect(metrics.totalCases).toBe(0);
    expect(metrics.openCases).toBe(0);
    expect(metrics.closedCases).toBe(0);
  });

  it("is deterministic -- the same input always produces the same output", () => {
    const cases = [
      row({ case_id: "a", state: "HUMAN_REVIEW" }),
      row({ case_id: "b", state: "FINALIZED", final_disposition: "BLOCK_HOLD" }),
      row({ case_id: "c", is_escalated_by_me: true }),
    ];
    expect(computeDashboardMetrics(cases)).toEqual(computeDashboardMetrics(cases));
  });
});
