import { useState } from "react";
import { Link } from "react-router-dom";
import { postTransaction, ApiError } from "../lib/api";
import { UploadDropzone } from "../components/UploadDropzone";
import { SingleTransactionPreview } from "../components/SingleTransactionPreview";
import { InvestigationResultPanel } from "../components/InvestigationResultPanel";
import { BatchInvestigationView } from "../components/BatchInvestigationView";
import { CaseDetailError } from "../components/StateNotices";
import type { ParsedRecordError } from "../lib/documentParser";
import type { JourneyPhase } from "../components/InvestigationJourney";
import type { Transaction, TransactionInvestigationResult } from "../lib/types";

/**
 * The public Transaction Investigation Console (build.md). Genuinely
 * public: no RequireAuth, no Firebase session read, no dependency on who
 * (if anyone) is signed into this browser. Its only backend call is the
 * real POST /transactions -- it never calls GET /cases/{case_id} and never
 * determines case ownership. The Analyst Portal (Case Queue / Case Detail,
 * behind RequireAuth) is a deliberately separate experience.
 */
export function InvestigationConsolePage() {
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [parseErrors, setParseErrors] = useState<ParsedRecordError[]>([]);

  const [singlePhase, setSinglePhase] = useState<JourneyPhase>("idle");
  const [singleResult, setSingleResult] = useState<TransactionInvestigationResult | null>(null);
  const [singleError, setSingleError] = useState<string | null>(null);

  function handleParsed(parsed: Transaction[], errors: ParsedRecordError[]) {
    setTransactions(parsed);
    setParseErrors(errors);
    setSinglePhase("idle");
    setSingleResult(null);
    setSingleError(null);
  }

  function reset() {
    setTransactions(null);
    setParseErrors([]);
    setSinglePhase("idle");
    setSingleResult(null);
    setSingleError(null);
  }

  async function investigateSingle() {
    if (!transactions || transactions.length !== 1) return;
    setSinglePhase("running");
    setSingleError(null);
    try {
      const result = await postTransaction(transactions[0]);
      setSingleResult(result);
      setSinglePhase("done");
    } catch (err) {
      setSingleError(err instanceof ApiError ? err.message : "Could not investigate this transaction.");
      setSinglePhase("request-failed");
    }
  }

  const isSingle = transactions !== null && transactions.length === 1;
  const isBatch = transactions !== null && transactions.length > 1;

  return (
    <div className="mx-auto max-w-[900px] px-6 py-10">
      <header className="mb-8 flex items-start justify-between">
        <div>
          <p className="text-[12px] tracking-wide text-[var(--color-text-faint)]">SENTINEL</p>
          <h1 className="mt-1 text-[22px] text-[var(--color-text)]">Transaction Investigation Console</h1>
          <p className="mt-2 max-w-[520px] text-[13px] text-[var(--color-text-muted)]">
            Upload transaction records and Sentinel will investigate them with evidence-driven AI and deterministic
            policy controls.
          </p>
          <p className="mt-1 max-w-[520px] text-[11px] text-[var(--color-text-faint)]">
            Prototype environment uses synthetic investigation context.
          </p>
        </div>
        <Link to="/login" className="mt-1 shrink-0 text-[12px] text-[var(--color-text-faint)] hover:text-[var(--color-text-muted)]">
          Analyst Login
        </Link>
      </header>

      {transactions === null && <UploadDropzone onParsed={handleParsed} />}

      {isSingle &&
        (singlePhase === "idle" ? (
          <SingleTransactionPreview transaction={transactions![0]} onInvestigate={investigateSingle} onReset={reset} />
        ) : (
          <div className="flex flex-col gap-4">
            {singleError && <CaseDetailError message={singleError} onRetry={() => setSinglePhase("idle")} />}
            <InvestigationResultPanel phase={singlePhase} result={singleResult} transaction={transactions![0]} />
            {(singlePhase === "done" || singlePhase === "request-failed") && (
              <button
                type="button"
                onClick={reset}
                className="self-start border border-[var(--color-rule)] px-3 py-2 text-[13px] text-[var(--color-text-muted)]"
              >
                Upload a different file
              </button>
            )}
          </div>
        ))}

      {isBatch && <BatchInvestigationView transactions={transactions!} parseErrors={parseErrors} onReset={reset} />}
    </div>
  );
}
