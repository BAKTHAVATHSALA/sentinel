import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { postTransaction, fetchTransactionStatus, ApiError } from "../lib/api";
import { UploadDropzone } from "../components/UploadDropzone";
import { SingleTransactionPreview } from "../components/SingleTransactionPreview";
import { InvestigationResultPanel } from "../components/InvestigationResultPanel";
import { BatchInvestigationView } from "../components/BatchInvestigationView";
import { CaseDetailError } from "../components/StateNotices";
import type { ParsedRecordError } from "../lib/documentParser";
import type { JourneyPhase } from "../components/InvestigationJourney";
import type { Transaction, TransactionInvestigationResult, TransactionLiveStatus } from "../lib/types";

/** How often to poll GET /transactions/{id}/status while the real POST
 * /transactions call is in flight. This is a poll of real, already-written
 * backend state (shared/pipeline/orchestrator.py's mid-request Firestore
 * writes) -- not a countdown standing in for the pipeline's actual work. */
const LIVE_STATUS_POLL_INTERVAL_MS = 400;

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
  const [singleLiveStatus, setSingleLiveStatus] = useState<TransactionLiveStatus | null>(null);
  const livePollHandle = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopLivePolling() {
    if (livePollHandle.current !== null) {
      clearInterval(livePollHandle.current);
      livePollHandle.current = null;
    }
  }

  // Stop polling if the console unmounts (navigating away) while a real
  // investigation is still in flight -- never leaves a timer calling
  // setState on an unmounted component.
  useEffect(() => stopLivePolling, []);

  function handleParsed(parsed: Transaction[], errors: ParsedRecordError[]) {
    stopLivePolling();
    setTransactions(parsed);
    setParseErrors(errors);
    setSinglePhase("idle");
    setSingleResult(null);
    setSingleError(null);
    setSingleLiveStatus(null);
  }

  function reset() {
    stopLivePolling();
    setTransactions(null);
    setParseErrors([]);
    setSinglePhase("idle");
    setSingleResult(null);
    setSingleError(null);
    setSingleLiveStatus(null);
  }

  async function investigateSingle() {
    if (!transactions || transactions.length !== 1) return;
    const transactionId = transactions[0].transaction_id;
    setSinglePhase("running");
    setSingleError(null);
    setSingleLiveStatus(null);

    // Poll the real backend's genuine, already-written per-stage progress
    // (services/api/main.py's GET /transactions/{id}/status) while the
    // single POST /transactions call below is in flight. A poll failure
    // (e.g. an older backend without this endpoint) is swallowed so the
    // journey falls back to its existing simultaneous-pulse display --
    // never surfaced as an investigation error.
    livePollHandle.current = setInterval(() => {
      fetchTransactionStatus(transactionId)
        .then(setSingleLiveStatus)
        .catch(() => {});
    }, LIVE_STATUS_POLL_INTERVAL_MS);

    try {
      const result = await postTransaction(transactions[0]);
      setSingleResult(result);
      setSinglePhase("done");
    } catch (err) {
      setSingleError(err instanceof ApiError ? err.message : "Could not investigate this transaction.");
      setSinglePhase("request-failed");
    } finally {
      stopLivePolling();
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
            Upload a transaction and let Sentinel investigate the evidence behind suspicious activity.
          </p>
          <p className="mt-1 max-w-[520px] text-[12px] text-[var(--color-text-faint)]">
            AI investigates and explains. Deterministic policy controls automated disposition.
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
            <InvestigationResultPanel
              phase={singlePhase}
              result={singleResult}
              transaction={transactions![0]}
              liveStatus={singleLiveStatus}
            />
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
