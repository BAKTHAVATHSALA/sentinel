import { describe, expect, it, vi } from "vitest";
import { runBatchInvestigation } from "./batchRunner";
import type { Transaction, TransactionInvestigationResult } from "./types";

function makeTransaction(id: string): Transaction {
  return {
    transaction_id: id,
    customer_id: "cust",
    account_id: "acc",
    card_id: "card",
    merchant_id: "merch",
    amount: "10.00",
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

function autoResolveResult(id: string): TransactionInvestigationResult {
  return {
    case_id: `case_${id}`,
    transaction_id: id,
    state: "AUTO_RESOLVED",
    outcome: null,
    rule_id: null,
    duplicate: false,
    assignment: null,
    decision_summary: {
      risk_assessment: "LOW",
      anomaly_tags: [],
      policy_rule_id: null,
      reasons: [],
      evidence_completeness: null,
      merchant_flagged: false,
    },
  };
}

describe("runBatchInvestigation", () => {
  it("never runs more than `concurrency` requests at once", async () => {
    const transactions = Array.from({ length: 10 }, (_, i) => makeTransaction(`tx_${i}`));
    let inFlight = 0;
    let maxInFlight = 0;

    const postTransactionFn = vi.fn(async (t: Transaction) => {
      inFlight++;
      maxInFlight = Math.max(maxInFlight, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 5));
      inFlight--;
      return autoResolveResult(t.transaction_id);
    });

    await runBatchInvestigation(transactions, { concurrency: 3, postTransactionFn });

    expect(maxInFlight).toBeLessThanOrEqual(3);
    expect(postTransactionFn).toHaveBeenCalledTimes(10);
  });

  it("reports progress incrementally as real completions land, ending at the true total with nothing left in flight", async () => {
    const transactions = Array.from({ length: 5 }, (_, i) => makeTransaction(`tx_${i}`));
    const completedCounts: number[] = [];
    let maxInFlightReported = 0;

    await runBatchInvestigation(transactions, {
      concurrency: 2,
      postTransactionFn: async (t) => autoResolveResult(t.transaction_id),
      onProgress: (progress) => {
        completedCounts.push(progress.completed);
        maxInFlightReported = Math.max(maxInFlightReported, progress.inFlight.length);
        expect(progress.completed).toBeLessThanOrEqual(progress.total);
      },
    });

    expect(completedCounts[completedCounts.length - 1]).toBe(5);
    expect(maxInFlightReported).toBeGreaterThan(0);
    expect(maxInFlightReported).toBeLessThanOrEqual(2);
  });

  it("reports which real transactions are currently in flight, not a simulated state", async () => {
    const transactions = [makeTransaction("tx_a"), makeTransaction("tx_b")];
    const inFlightIds: string[][] = [];
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });

    const run = runBatchInvestigation(transactions, {
      concurrency: 2,
      postTransactionFn: async (t) => {
        await gate;
        return autoResolveResult(t.transaction_id);
      },
      onProgress: (progress) => inFlightIds.push(progress.inFlight.map((t) => t.transaction_id)),
    });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(inFlightIds[inFlightIds.length - 1].sort()).toEqual(["tx_a", "tx_b"]);

    release();
    await run;
  });

  it("does not abort the batch when one transaction fails, and reports it as failed", async () => {
    const transactions = [makeTransaction("tx_ok_1"), makeTransaction("tx_bad"), makeTransaction("tx_ok_2")];

    const results = await runBatchInvestigation(transactions, {
      concurrency: 3,
      postTransactionFn: async (t) => {
        if (t.transaction_id === "tx_bad") throw new Error("backend unavailable");
        return autoResolveResult(t.transaction_id);
      },
    });

    expect(results).toHaveLength(3);
    const failed = results.find((r) => r.transaction.transaction_id === "tx_bad");
    expect(failed?.status).toBe("failed");
    expect(failed?.error).toBe("backend unavailable");
    expect(results.filter((r) => r.status === "completed")).toHaveLength(2);
  });

  it("preserves input order in the returned results regardless of completion order", async () => {
    const transactions = Array.from({ length: 6 }, (_, i) => makeTransaction(`tx_${i}`));
    const results = await runBatchInvestigation(transactions, {
      concurrency: 3,
      // Reverse-index transactions resolve faster, to actually exercise out-of-order completion.
      postTransactionFn: async (t) => {
        const i = Number(t.transaction_id.split("_")[1]);
        await new Promise((resolve) => setTimeout(resolve, (6 - i) % 3));
        return autoResolveResult(t.transaction_id);
      },
    });

    expect(results.map((r) => r.transaction.transaction_id)).toEqual(transactions.map((t) => t.transaction_id));
  });
});
