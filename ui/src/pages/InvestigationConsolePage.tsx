import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { postTransaction, fetchTransactionStatus, ApiError } from "../lib/api";
import { fetchDemoSampleTransactions, ensureDemoSession } from "../lib/demoApi";
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [isDemoMode, setIsDemoMode] = useState(() => searchParams.get("demo") === "true");

  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [parseErrors, setParseErrors] = useState<ParsedRecordError[]>([]);

  const [singlePhase, setSinglePhase] = useState<JourneyPhase>("idle");
  const [singleResult, setSingleResult] = useState<TransactionInvestigationResult | null>(null);
  const [singleError, setSingleError] = useState<string | null>(null);
  const [singleLiveStatus, setSingleLiveStatus] = useState<TransactionLiveStatus | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const livePollHandle = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopLivePolling() {
    if (livePollHandle.current !== null) {
      clearInterval(livePollHandle.current);
      livePollHandle.current = null;
    }
  }

  // A status call can take several seconds (Firestore round trips); never
  // start a new one while the previous is pending, or they pile up and
  // exhaust the browser's per-host connections, stalling later requests.
  function startLivePolling(transactionId: string) {
    let inFlight = false;
    livePollHandle.current = setInterval(() => {
      if (inFlight) return;
      inFlight = true;
      fetchTransactionStatus(transactionId)
        .then(setSingleLiveStatus)
        .catch(() => {})
        .finally(() => {
          inFlight = false;
        });
    }, LIVE_STATUS_POLL_INTERVAL_MS);
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

  async function handleRunDemoTransaction(type: "clean" | "high_risk") {
    setDemoLoading(true);
    setSingleError(null);
    setSingleResult(null);
    setSingleLiveStatus(null);
    stopLivePolling();

    try {
      await ensureDemoSession();
      let tx: Transaction;
      try {
        const samples = await fetchDemoSampleTransactions();
        const baseTx = type === "clean" ? samples.clean : samples.high_risk;
        tx = {
          ...baseTx,
          transaction_id: `tx_demo_${type === "clean" ? "clean" : "fraud"}_${Date.now()}`,
        };
      } catch {
        tx = {
          transaction_id: `tx_demo_${type === "clean" ? "clean" : "fraud"}_${Date.now()}`,
          customer_id: type === "clean" ? "cust_sc_clean" : "cust_sc_flagship",
          account_id: "acc_demo",
          card_id: "card_demo",
          merchant_id: type === "clean" ? "merch_standard_clean" : "merch_flagship_electronics",
          amount: type === "clean" ? "75.00" : "1249.99",
          currency: "USD",
          timestamp: new Date().toISOString(),
          payment_rail: "CARD_CNP",
          direction: "OUTGOING",
          authorization_stage: "PRE_AUTH",
          device_id: type === "clean" ? "dev_46048" : "dev_compromised_99",
          ip_address: type === "clean" ? "198.51.100.72" : "203.0.113.19",
          geo: { lat: "37.7749", lon: "-122.4194", country: "USA" },
          channel: "WEB",
          merchant_category: "electronics",
          card_present: false,
        };
      }

      setTransactions([tx]);
      setSinglePhase("running");

      // Poll the real backend's genuine, already-written per-stage progress
      startLivePolling(tx.transaction_id);

      const result = await postTransaction(tx);
      setSingleResult(result);
      setSinglePhase("done");
    } catch (err: any) {
      setSingleError(err instanceof ApiError ? err.message : "Could not investigate this demo transaction.");
      setSinglePhase("request-failed");
    } finally {
      stopLivePolling();
      setDemoLoading(false);
    }
  }

  async function investigateSingle() {
    if (!transactions || transactions.length !== 1) return;
    const transactionId = transactions[0].transaction_id;
    setSinglePhase("running");
    setSingleError(null);
    setSingleLiveStatus(null);

    startLivePolling(transactionId);

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
      <header className="mb-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[12px] tracking-wide text-[var(--color-text-faint)]">SENTINEL</p>
            {isDemoMode && (
              <span className="rounded bg-[var(--color-caution-soft)] px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-[var(--color-caution)]">
                DEMO MODE
              </span>
            )}
          </div>
          <h1 className="mt-1 text-[22px] text-[var(--color-text)]">
            {isDemoMode ? "Sentinel Demo Console" : "Transaction Investigation Console"}
          </h1>
          <p className="mt-2 max-w-[520px] text-[13px] text-[var(--color-text-muted)]">
            {isDemoMode
              ? "Run synthetic transactions through Sentinel's live backend pipeline to observe genuine investigation stages."
              : "Upload a transaction and let Sentinel investigate the evidence behind suspicious activity."}
          </p>
          <p className="mt-1 max-w-[520px] text-[12px] text-[var(--color-text-faint)]">
            AI investigates and explains. Deterministic policy controls automated disposition.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {!isDemoMode ? (
            <>
              <Link to="/login" className="mt-1 shrink-0 text-[12px] text-[var(--color-text-faint)] hover:text-[var(--color-text-muted)]">
                Analyst Login
              </Link>
              <button
                type="button"
                onClick={() => {
                  setIsDemoMode(true);
                  setSearchParams({ demo: "true" });
                  reset();
                }}
                className="border border-[var(--color-caution)] bg-[var(--color-caution-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--color-caution)] hover:bg-[var(--color-surface-raised)]"
              >
                Try Demo
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => {
                setIsDemoMode(false);
                setSearchParams({});
                reset();
              }}
              className="border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-2.5 py-1 text-[11px] font-medium text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              Exit Demo Mode
            </button>
          )}
        </div>
      </header>

      {/* When in Demo Mode: ONLY this demo banner is visible (no dropzone, no explore demo cases button) */}
      {isDemoMode && (
        <div className="mb-6 border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-[var(--color-caution-soft)] px-2 py-0.5 text-[10px] font-semibold tracking-wide text-[var(--color-caution)]">
                  HACKATHON DEMO MODE
                </span>
                <span className="text-[13px] font-medium text-[var(--color-text)]">Explore Without Credentials</span>
              </div>
              <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
                Run clean or high-risk synthetic transactions live through the real backend.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <button
                type="button"
                disabled={demoLoading}
                onClick={() => handleRunDemoTransaction("clean")}
                className="border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-2.5 py-1 text-[12px] text-[var(--color-text)] hover:border-[var(--color-text-muted)] disabled:opacity-50"
              >
                {demoLoading && singlePhase === "running" && transactions?.[0]?.transaction_id.includes("clean")
                  ? "Investigating..."
                  : "Run Clean Transaction"}
              </button>
              <button
                type="button"
                disabled={demoLoading}
                onClick={() => handleRunDemoTransaction("high_risk")}
                className="border border-[var(--color-caution)] bg-[var(--color-caution-soft)] px-2.5 py-1 text-[12px] font-medium text-[var(--color-caution)] hover:bg-[var(--color-surface-raised)] disabled:opacity-50"
              >
                {demoLoading && singlePhase === "running" && !transactions?.[0]?.transaction_id.includes("clean")
                  ? "Investigating..."
                  : "Run High-Risk Transaction"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* In standard mode, render normal dropzone / manual upload */}
      {!isDemoMode && transactions === null && <UploadDropzone onParsed={handleParsed} />}

      {/* Investigation results panel for single transaction (in both demo and standard mode) */}
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
            {!isDemoMode && (singlePhase === "done" || singlePhase === "request-failed") && (
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

      {!isDemoMode && isBatch && (
        <BatchInvestigationView transactions={transactions!} parseErrors={parseErrors} onReset={reset} />
      )}
    </div>
  );
}
