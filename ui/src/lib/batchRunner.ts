import { postTransaction } from "./api";
import type { Transaction, TransactionInvestigationResult } from "./types";

/**
 * Bounded-concurrency batch execution over the real POST /transactions
 * endpoint (Section 12: "controlled concurrency ... small bounded worker
 * pool"). Every transaction is a real HTTP request through the real
 * pipeline -- no frontend-only outcomes, no faked policy results. One
 * transaction's failure never aborts the rest of the batch (Section 31).
 */

export interface BatchItemResult {
  transaction: Transaction;
  status: "completed" | "failed";
  result?: TransactionInvestigationResult;
  error?: string;
}

export interface BatchProgress {
  completed: number;
  total: number;
  results: BatchItemResult[];
  /** Transactions whose real POST /transactions request is currently
   * pending -- not a simulated "currently investigating" state, an actual
   * snapshot of in-flight requests (Section 24). */
  inFlight: Transaction[];
}

export interface RunBatchOptions {
  concurrency: number;
  onProgress?: (progress: BatchProgress) => void;
  /** Injected for tests; defaults to the real postTransaction. */
  postTransactionFn?: (transaction: Transaction) => Promise<TransactionInvestigationResult>;
}

export async function runBatchInvestigation(transactions: Transaction[], options: RunBatchOptions): Promise<BatchItemResult[]> {
  const post = options.postTransactionFn ?? postTransaction;
  const results: BatchItemResult[] = new Array(transactions.length);
  const inFlight = new Map<number, Transaction>();
  let nextIndex = 0;
  let completed = 0;

  function reportProgress() {
    options.onProgress?.({
      completed,
      total: transactions.length,
      results: results.filter((r) => r !== undefined),
      inFlight: Array.from(inFlight.values()),
    });
  }

  async function worker(): Promise<void> {
    for (;;) {
      const index = nextIndex;
      nextIndex += 1;
      if (index >= transactions.length) return;
      const transaction = transactions[index];
      inFlight.set(index, transaction);
      reportProgress();
      try {
        const result = await post(transaction);
        results[index] = { transaction, status: "completed", result };
      } catch (err) {
        results[index] = { transaction, status: "failed", error: err instanceof Error ? err.message : "Investigation failed" };
      }
      inFlight.delete(index);
      completed += 1;
      reportProgress();
    }
  }

  const workerCount = Math.max(1, Math.min(options.concurrency, transactions.length || 1));
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return results;
}
