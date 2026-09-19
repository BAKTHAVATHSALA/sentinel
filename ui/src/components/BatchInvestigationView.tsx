import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { AnomalyTagChip } from "./AnomalyTagChip";
import { runBatchInvestigation, type BatchItemResult, type BatchProgress } from "../lib/batchRunner";
import type { ParsedRecordError } from "../lib/documentParser";
import type { RiskBand, Transaction } from "../lib/types";

const BATCH_CONCURRENCY = 3;

type Stage = "preview" | "running" | "complete";

function formatElapsed(ms: number): string {
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

const RISK_TEXT_STYLE: Record<RiskBand, string> = {
  LOW: "text-[var(--color-stable)]",
  MEDIUM: "text-[var(--color-caution)]",
  HIGH: "text-[var(--color-critical)]",
};

function outcomeLabel(item: BatchItemResult): { text: string; style: string } {
  if (item.status === "failed") return { text: "FAILED", style: "text-[var(--color-critical)]" };
  if (item.result?.state === "HUMAN_REVIEW") return { text: "HUMAN REVIEW", style: "text-[var(--color-caution)]" };
  if (item.result?.state === "AUTO_RESOLVED") return { text: "AUTO RESOLVED", style: "text-[var(--color-stable)]" };
  return { text: item.result?.state ?? "UNKNOWN", style: "text-[var(--color-text)]" };
}

/**
 * Live batch operations view (build.md Sections 9/11/12/23-27). Every
 * number here is computed from real BatchProgress state produced by
 * runBatchInvestigation, which sends every transaction through the real
 * POST /transactions -- nothing here is hardcoded or predicted ahead of
 * execution.
 */
export function BatchInvestigationView({
  transactions,
  parseErrors,
  onReset,
}: {
  transactions: Transaction[];
  parseErrors: ParsedRecordError[];
  onReset: () => void;
}) {
  const [stage, setStage] = useState<Stage>("preview");
  const [progress, setProgress] = useState<BatchProgress>({ completed: 0, total: transactions.length, results: [], inFlight: [] });
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  async function handleRun() {
    setStage("running");
    const startedAt = performance.now();
    await runBatchInvestigation(transactions, { concurrency: BATCH_CONCURRENCY, onProgress: setProgress });
    setElapsedMs(performance.now() - startedAt);
    setStage("complete");
  }

  if (stage === "preview") {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-[16px] text-[var(--color-text)]">TRANSACTION BATCH</h2>
          <p className="text-[13px] text-[var(--color-text-muted)]">{transactions.length} transactions detected</p>
        </div>

        {parseErrors.length > 0 && (
          <div className="border border-[var(--color-caution)] bg-[var(--color-caution-soft)] p-3 text-[12px] text-[var(--color-caution)]">
            {parseErrors.length} record{parseErrors.length === 1 ? "" : "s"} could not be parsed and will be skipped:
            <ul className="mt-1 max-h-24 overflow-y-auto">
              {parseErrors.map((e, i) => (
                <li key={i}>
                  TRANSACTION {e.recordLabel}: {e.reason}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="overflow-x-auto border border-[var(--color-rule)]">
          <table className="w-full min-w-[560px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--color-rule)] text-[12px] text-[var(--color-text-muted)]">
                <th className="px-3 py-2 font-normal">Transaction</th>
                <th className="px-3 py-2 font-normal">Amount</th>
                <th className="px-3 py-2 font-normal">Merchant</th>
                <th className="px-3 py-2 font-normal">Channel</th>
                <th className="px-3 py-2 font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.transaction_id} className="border-b border-[var(--color-rule)] last:border-0">
                  <td className="px-3 py-2 font-mono text-[12px]">{t.transaction_id}</td>
                  <td className="px-3 py-2">
                    {t.currency} {t.amount}
                  </td>
                  <td className="px-3 py-2 text-[var(--color-text-muted)]">{t.merchant_category}</td>
                  <td className="px-3 py-2 text-[var(--color-text-muted)]">{t.channel}</td>
                  <td className="px-3 py-2 text-[var(--color-stable)]">Ready</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleRun}
            className="border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-4 py-2 text-[13px] text-[var(--color-text)]"
          >
            Run Investigation
          </button>
          <button type="button" onClick={onReset} className="border border-[var(--color-rule)] px-3 py-2 text-[13px] text-[var(--color-text-muted)]">
            Upload a different file
          </button>
        </div>
      </div>
    );
  }

  const autoResolvedCount = progress.results.filter((r) => r.status === "completed" && r.result?.state === "AUTO_RESOLVED").length;
  const humanReviewCount = progress.results.filter((r) => r.status === "completed" && r.result?.state === "HUMAN_REVIEW").length;
  const failedCount = progress.results.filter((r) => r.status === "failed").length;
  const processingCount = progress.total - progress.completed;
  const percent = progress.total === 0 ? 0 : Math.round((progress.completed / progress.total) * 100);

  // Risk (LOW/MEDIUM/HIGH) and disposition (AUTO_RESOLVED/HUMAN_REVIEW) are
  // deliberately counted separately here -- a real batch can show e.g.
  // LOW=10 but AUTO-RESOLVED=5, because P-004 (v1.3) additionally requires
  // a clean (zero-anomaly-tag) transaction, not merely a LOW risk_assessment.
  // Every count below is read directly from each item's real
  // decision_summary.risk_assessment; nothing is inferred from the PDF,
  // anomaly tags, policy rules, or transaction_id.
  const riskCounts: Record<RiskBand, number> = { LOW: 0, MEDIUM: 0, HIGH: 0 };
  for (const item of progress.results) {
    const band = item.status === "completed" ? item.result?.decision_summary.risk_assessment : null;
    if (band) riskCounts[band] += 1;
  }

  const workload = new Map<string, number>();
  for (const item of progress.results) {
    const name = item.status === "completed" ? item.result?.assignment?.analyst_name : undefined;
    if (name) workload.set(name, (workload.get(name) ?? 0) + 1);
  }
  const workloadRows = Array.from(workload.entries()).sort((a, b) => b[1] - a[1]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-[16px] text-[var(--color-text)]">{stage === "running" ? "SENTINEL INVESTIGATION" : "INVESTIGATION COMPLETE"}</h2>
        <p className="text-[13px] text-[var(--color-text-muted)]">
          {stage === "running" ? "Processing transaction batch" : `${progress.total} transactions processed`}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <div className="h-2 w-full border border-[var(--color-rule)]">
          <div className="h-full bg-[var(--color-stable)] transition-[width] duration-300" style={{ width: `${percent}%` }} />
        </div>
        <p className="text-[13px] text-[var(--color-text-muted)]">
          {progress.completed} / {progress.total} completed
          {stage === "complete" && elapsedMs !== null && (
            <span className="ml-3 text-[var(--color-text-faint)]">
              Batch completed in {formatElapsed(elapsedMs)} (this demo run's measured wall-clock time, not a throughput benchmark)
            </span>
          )}
        </p>
      </div>

      {stage === "complete" && (
        <div className="flex flex-col gap-1.5">
          <h3 className="text-[12px] text-[var(--color-text-muted)]">
            RISK DISTRIBUTION <span className="text-[var(--color-text-faint)]">&middot; how risky Detection judged each transaction</span>
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "LOW", value: riskCounts.LOW, style: "text-[var(--color-stable)]" },
              { label: "MEDIUM", value: riskCounts.MEDIUM, style: "text-[var(--color-caution)]" },
              { label: "HIGH", value: riskCounts.HIGH, style: "text-[var(--color-critical)]" },
            ].map((s) => (
              <div key={s.label} data-testid={`batch-risk-${s.label}`} className="border border-[var(--color-rule)] bg-[var(--color-surface)] p-3 text-center">
                <p className={`text-[20px] ${s.style}`}>{s.value}</p>
                <p className="text-[11px] text-[var(--color-text-muted)]">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <h3 className="text-[12px] text-[var(--color-text-muted)]">
          ROUTING <span className="text-[var(--color-text-faint)]">&middot; what the deterministic policy decided to do</span>
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "AUTO RESOLVED", value: autoResolvedCount, style: "text-[var(--color-stable)]" },
            { label: "HUMAN REVIEW", value: humanReviewCount, style: "text-[var(--color-caution)]" },
            { label: "PROCESSING", value: processingCount, style: "text-[var(--color-text-muted)]" },
            { label: "FAILED", value: failedCount, style: "text-[var(--color-critical)]" },
          ].map((s) => (
            <div key={s.label} data-testid={`batch-stat-${s.label}`} className="border border-[var(--color-rule)] bg-[var(--color-surface)] p-3 text-center">
              <p className={`text-[20px] ${s.style}`}>{s.value}</p>
              <p className="text-[11px] text-[var(--color-text-muted)]">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {stage === "running" && progress.inFlight.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-[12px] text-[var(--color-text-muted)]">CURRENTLY INVESTIGATING</h3>
          <div className="flex flex-wrap gap-2">
            {progress.inFlight.map((t) => (
              <div key={t.transaction_id} className="border border-[var(--color-rule)] bg-[var(--color-surface)] p-3 text-[12px]">
                <p className="font-mono text-[var(--color-text)]">{t.transaction_id}</p>
                <p className="text-[var(--color-text-muted)]">
                  {t.currency} {t.amount} &middot; {t.merchant_category} &middot; {t.channel}
                </p>
                <p className="mt-1 text-[var(--color-text-faint)]">Evidence investigation in progress...</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {stage === "complete" && workloadRows.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <h3 className="text-[12px] text-[var(--color-text-muted)]">ANALYST WORKLOAD</h3>
          {workloadRows.map(([name, count]) => (
            <div key={name} className="flex justify-between border-b border-[var(--color-rule)] py-1 text-[13px]">
              <span className="text-[var(--color-text)]">{name}</span>
              <span className="text-[var(--color-text-muted)]">
                {count} case{count === 1 ? "" : "s"}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-1">
        <h3 className="text-[12px] text-[var(--color-text-muted)]">RESULTS</h3>
        <div className="overflow-x-auto border border-[var(--color-rule)]">
          <table className="w-full min-w-[640px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-[var(--color-rule)] text-[12px] text-[var(--color-text-muted)]">
                <th className="px-3 py-2 font-normal">Transaction</th>
                <th className="px-3 py-2 font-normal">Amount</th>
                <th className="px-3 py-2 font-normal">Risk</th>
                <th className="px-3 py-2 font-normal">Routing</th>
                <th className="px-3 py-2 font-normal">Assigned analyst</th>
              </tr>
            </thead>
            <tbody>
              {progress.results.map((item) => {
                const outcome = outcomeLabel(item);
                const risk = item.status === "completed" ? item.result?.decision_summary.risk_assessment : null;
                const expanded = expandedId === item.transaction.transaction_id;
                return (
                  <Fragment key={item.transaction.transaction_id}>
                    <tr
                      className="cursor-pointer border-b border-[var(--color-rule)] last:border-0 hover:bg-[var(--color-surface-raised)]"
                      onClick={() => setExpandedId(expanded ? null : item.transaction.transaction_id)}
                    >
                      <td className="px-3 py-2 font-mono text-[12px]">{item.transaction.transaction_id}</td>
                      <td className="px-3 py-2">
                        {item.transaction.currency} {item.transaction.amount}
                      </td>
                      <td className={`px-3 py-2 ${risk ? RISK_TEXT_STYLE[risk] : "text-[var(--color-text-faint)]"}`}>{risk ?? "–"}</td>
                      <td className={`px-3 py-2 ${outcome.style}`}>{outcome.text}</td>
                      <td className="px-3 py-2 text-[var(--color-text-muted)]">
                        {item.status === "completed" && item.result?.assignment?.analyst_name}
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="border-b border-[var(--color-rule)] bg-[var(--color-surface-raised)]">
                        <td colSpan={5} className="px-3 py-3 text-[12px] text-[var(--color-text-muted)]">
                          {item.status === "failed" ? (
                            <p className="text-[var(--color-critical)]">{item.error}</p>
                          ) : (
                            <>
                              <p>Merchant: {item.transaction.merchant_id}</p>
                              <p>Device: {item.transaction.device_id}</p>
                              <p>
                                Geo: {item.transaction.geo.country} ({item.transaction.geo.lat}, {item.transaction.geo.lon})
                              </p>
                              <p>Authorization stage: {item.transaction.authorization_stage}</p>
                              {item.result && item.result.decision_summary.anomaly_tags.length > 0 && (
                                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                                  <span>Signals:</span>
                                  {item.result.decision_summary.anomaly_tags.map((tag) => (
                                    <AnomalyTagChip key={tag} tag={tag} />
                                  ))}
                                </div>
                              )}
                              {item.result?.case_id && (
                                <Link to={`/case/${encodeURIComponent(item.result.case_id)}`} className="mt-1 inline-block text-[var(--color-text)] underline">
                                  Open Case
                                </Link>
                              )}
                            </>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {stage === "complete" && (
        <button type="button" onClick={onReset} className="self-start border border-[var(--color-rule)] px-3 py-2 text-[13px] text-[var(--color-text-muted)]">
          Upload a different file
        </button>
      )}
    </div>
  );
}
