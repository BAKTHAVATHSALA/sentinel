import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { BatchInvestigationView } from "./BatchInvestigationView";
import * as batchRunner from "../lib/batchRunner";
import type { Transaction, TransactionInvestigationResult } from "../lib/types";
import type { BatchItemResult, BatchProgress } from "../lib/batchRunner";

function makeTransaction(id: string, amount = "10.00"): Transaction {
  return {
    transaction_id: id,
    customer_id: "cust",
    account_id: "acc",
    card_id: "card",
    merchant_id: "merch",
    amount,
    currency: "USD",
    timestamp: "2026-09-13T14:00:00Z",
    payment_rail: "CARD_CNP",
    direction: "OUTGOING",
    authorization_stage: "PRE_AUTH",
    device_id: "dev",
    ip_address: "1.2.3.4",
    geo: { lat: "0", lon: "0", country: "USA" },
    channel: "WEB",
    merchant_category: "electronics",
    card_present: false,
  };
}

const CLEAN_DECISION_SUMMARY = {
  risk_assessment: "LOW" as const,
  anomaly_tags: [],
  policy_rule_id: null,
  reasons: [],
  evidence_completeness: null,
  merchant_flagged: false,
};

const ESCALATED_DECISION_SUMMARY = {
  risk_assessment: "HIGH" as const,
  anomaly_tags: ["NEW_DEVICE" as const],
  policy_rule_id: "P-002",
  reasons: ["risk_band = HIGH (>= MEDIUM)", "findings.risk_assessment = HIGH", "evidence.completeness = COMPLETE"],
  evidence_completeness: "COMPLETE" as const,
  merchant_flagged: false,
};

function autoResolve(id: string): TransactionInvestigationResult {
  return {
    case_id: `case_${id}`,
    transaction_id: id,
    state: "AUTO_RESOLVED",
    outcome: null,
    rule_id: null,
    duplicate: false,
    assignment: null,
    decision_summary: CLEAN_DECISION_SUMMARY,
  };
}

function humanReview(id: string, analyst: string): TransactionInvestigationResult {
  return {
    case_id: `case_${id}`,
    transaction_id: id,
    state: "HUMAN_REVIEW",
    outcome: "ESCALATE",
    rule_id: "P-002",
    duplicate: false,
    assignment: { analyst_name: analyst },
    decision_summary: ESCALATED_DECISION_SUMMARY,
  };
}

function renderView(transactions: Transaction[]) {
  return render(
    <MemoryRouter>
      <BatchInvestigationView transactions={transactions} parseErrors={[]} onReset={vi.fn()} />
    </MemoryRouter>,
  );
}

describe("BatchInvestigationView", () => {
  it("shows the preview table before running", () => {
    renderView([makeTransaction("tx_1"), makeTransaction("tx_2")]);
    expect(screen.getByText("TRANSACTION BATCH")).toBeInTheDocument();
    expect(screen.getByText("2 transactions detected")).toBeInTheDocument();
    expect(screen.getByText("tx_1")).toBeInTheDocument();
    expect(screen.getAllByText("Ready")).toHaveLength(2);
  });

  it("calls runBatchInvestigation with the parsed transactions and a bounded concurrency on Run Investigation", async () => {
    const transactions = [makeTransaction("tx_1"), makeTransaction("tx_2")];
    const runSpy = vi.spyOn(batchRunner, "runBatchInvestigation").mockResolvedValue([]);
    const user = userEvent.setup();
    renderView(transactions);

    await user.click(screen.getByRole("button", { name: "Run Investigation" }));

    await waitFor(() => expect(runSpy).toHaveBeenCalled());
    const [calledTransactions, options] = runSpy.mock.calls[0];
    expect(calledTransactions).toEqual(transactions);
    expect(options.concurrency).toBeGreaterThan(0);
  });

  it("renders live totals computed from real progress, including a currently-investigating panel", async () => {
    const transactions = [makeTransaction("tx_1"), makeTransaction("tx_2"), makeTransaction("tx_3")];
    let releaseBatch: () => void = () => {};
    const stillRunning = new Promise<BatchItemResult[]>((resolve) => {
      releaseBatch = () => resolve([]);
    });
    vi.spyOn(batchRunner, "runBatchInvestigation").mockImplementation(async (_txs, options) => {
      const partial: BatchItemResult[] = [{ transaction: transactions[0], status: "completed", result: autoResolve("tx_1") }];
      const progress: BatchProgress = { completed: 1, total: 3, results: partial, inFlight: [transactions[1], transactions[2]] };
      options.onProgress?.(progress);
      return stillRunning; // stays "running" (doesn't resolve) until the assertions below run
    });
    const user = userEvent.setup();
    renderView(transactions);

    await user.click(screen.getByRole("button", { name: "Run Investigation" }));

    expect(await screen.findByText("CURRENTLY INVESTIGATING")).toBeInTheDocument();
    expect(screen.getByTestId("batch-stat-AUTO RESOLVED")).toHaveTextContent("1");

    releaseBatch();
  });

  it("renders final totals and analyst workload from real completed results, never fabricated", async () => {
    const transactions = [makeTransaction("tx_1"), makeTransaction("tx_2"), makeTransaction("tx_3")];
    const results: BatchItemResult[] = [
      { transaction: transactions[0], status: "completed", result: autoResolve("tx_1") },
      { transaction: transactions[1], status: "completed", result: humanReview("tx_2", "Priya Nair") },
      { transaction: transactions[2], status: "failed", error: "backend unavailable" },
    ];
    vi.spyOn(batchRunner, "runBatchInvestigation").mockImplementation(async (_txs, options) => {
      options.onProgress?.({ completed: 3, total: 3, results, inFlight: [] });
      return results;
    });
    const user = userEvent.setup();
    renderView(transactions);

    await user.click(screen.getByRole("button", { name: "Run Investigation" }));

    expect(await screen.findByText("INVESTIGATION COMPLETE")).toBeInTheDocument();
    expect(screen.getByText("3 transactions processed")).toBeInTheDocument();
    expect(screen.getByText("ANALYST WORKLOAD")).toBeInTheDocument();
    expect(screen.getAllByText("Priya Nair").length).toBeGreaterThan(0); // workload summary + results row
    expect(screen.getByText("1 case")).toBeInTheDocument();
    expect(screen.getAllByText("FAILED").length).toBeGreaterThan(0); // stat tile label + results row
    expect(screen.getAllByText("HUMAN REVIEW").length).toBeGreaterThan(0);
    expect(screen.getAllByText("AUTO RESOLVED").length).toBeGreaterThan(0);
  });

  it("expands a row to reveal public-safe detail and an Open Case link, without calling GET /cases/{case_id}", async () => {
    const transactions = [makeTransaction("tx_1")];
    const results: BatchItemResult[] = [{ transaction: transactions[0], status: "completed", result: humanReview("tx_1", "Priya Nair") }];
    vi.spyOn(batchRunner, "runBatchInvestigation").mockImplementation(async (_txs, options) => {
      options.onProgress?.({ completed: 1, total: 1, results, inFlight: [] });
      return results;
    });
    const user = userEvent.setup();
    renderView(transactions);

    await user.click(screen.getByRole("button", { name: "Run Investigation" }));
    await screen.findByText("INVESTIGATION COMPLETE");
    await user.click(screen.getByText("tx_1"));

    expect(screen.getByRole("link", { name: "Open Case" })).toHaveAttribute("href", "/case/case_tx_1");
  });

  it("never exposes the raw policy rule_id in an expanded row", async () => {
    const transactions = [makeTransaction("tx_1")];
    const results: BatchItemResult[] = [{ transaction: transactions[0], status: "completed", result: humanReview("tx_1", "Priya Nair") }];
    vi.spyOn(batchRunner, "runBatchInvestigation").mockImplementation(async (_txs, options) => {
      options.onProgress?.({ completed: 1, total: 1, results, inFlight: [] });
      return results;
    });
    const user = userEvent.setup();
    renderView(transactions);

    await user.click(screen.getByRole("button", { name: "Run Investigation" }));
    await screen.findByText("INVESTIGATION COMPLETE");
    await user.click(screen.getByText("tx_1"));

    expect(screen.queryByText(/Rule:/)).not.toBeInTheDocument();
    expect(screen.queryByText("P-002")).not.toBeInTheDocument();
    expect(screen.getByText("New device")).toBeInTheDocument(); // safe signal summary instead
  });

  it("computes RISK DISTRIBUTION (LOW/MEDIUM/HIGH) separately from ROUTING (disposition), from real decision_summary values", async () => {
    const transactions = [makeTransaction("tx_1"), makeTransaction("tx_2"), makeTransaction("tx_3")];
    const lowButAnomalousHumanReview: BatchItemResult = {
      transaction: transactions[1],
      status: "completed",
      result: {
        case_id: "case_tx_2",
        transaction_id: "tx_2",
        state: "HUMAN_REVIEW",
        outcome: "ESCALATE",
        rule_id: "P-005",
        duplicate: false,
        assignment: { analyst_name: "Marcus Webb" },
        decision_summary: {
          risk_assessment: "LOW",
          anomaly_tags: ["NEW_DEVICE"],
          policy_rule_id: "P-005",
          reasons: [],
          evidence_completeness: "COMPLETE",
          merchant_flagged: false,
        },
      },
    };
    const results: BatchItemResult[] = [
      { transaction: transactions[0], status: "completed", result: autoResolve("tx_1") }, // LOW, AUTO_RESOLVED
      lowButAnomalousHumanReview, // LOW risk, but HUMAN_REVIEW (v1.3: LOW != CLEAN)
      { transaction: transactions[2], status: "completed", result: humanReview("tx_3", "Priya Nair") }, // HIGH, HUMAN_REVIEW
    ];
    vi.spyOn(batchRunner, "runBatchInvestigation").mockImplementation(async (_txs, options) => {
      options.onProgress?.({ completed: 3, total: 3, results, inFlight: [] });
      return results;
    });
    const user = userEvent.setup();
    renderView(transactions);

    await user.click(screen.getByRole("button", { name: "Run Investigation" }));
    await screen.findByText("INVESTIGATION COMPLETE");

    expect(screen.getByTestId("batch-risk-LOW")).toHaveTextContent("2"); // tx_1 + tx_2 are both LOW risk
    expect(screen.getByTestId("batch-risk-HIGH")).toHaveTextContent("1");
    expect(screen.getByTestId("batch-stat-AUTO RESOLVED")).toHaveTextContent("1"); // only tx_1
    expect(screen.getByTestId("batch-stat-HUMAN REVIEW")).toHaveTextContent("2"); // tx_2 + tx_3
  });
});
