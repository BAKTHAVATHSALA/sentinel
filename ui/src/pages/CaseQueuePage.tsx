import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDashboardCases, ApiError } from "../lib/api";
import { AnalystNavBar } from "../components/AnalystNavBar";
import { DashboardMetricCards } from "../components/DashboardMetricCards";
import { QueueTable } from "../components/QueueTable";
import { CaseDetailError } from "../components/StateNotices";
import { useAnalystIdentity } from "../lib/analystIdentity";
import { computeDashboardMetrics } from "../lib/dashboardMetrics";
import type { QueueCaseSummary } from "../lib/types";

export function CaseQueuePage() {
  const [cases, setCases] = useState<QueueCaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const identity = useAnalystIdentity();

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchDashboardCases()
      .then((data) => {
        if (!cancelled) setCases(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Could not load the queue.");
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  // The queue table shows exactly what plain GET /cases always has: this
  // analyst's own open (HUMAN_REVIEW) cases -- escalated-away cases and
  // closed cases are still excluded from the table, only the metric cards
  // below use the full fetched set. Deriving this client-side from the same
  // single fetch avoids a second request for the same underlying data.
  const queueRows = cases?.filter((c) => c.state === "HUMAN_REVIEW" && !c.is_escalated_by_me) ?? null;

  return (
    <div className="flex h-screen flex-col">
      <AnalystNavBar />

      <div className="mx-auto w-full max-w-[1400px] px-6 py-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-[20px] text-[var(--color-text)]">Case queue</h1>
          <Link
            to="/investigate"
            className="border border-[var(--color-rule)] px-2 py-1 text-[12px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            Transaction console
          </Link>
        </div>

        {error && <CaseDetailError message={error} onRetry={() => setReloadToken((t) => t + 1)} />}

        {!error && cases === null && (
          <div className="text-[13px] text-[var(--color-text-faint)]">Loading queue...</div>
        )}

        {!error && cases !== null && (
          <div className="mb-5">
            <DashboardMetricCards
              metrics={computeDashboardMetrics(cases)}
              showEscalatedToSenior={identity?.role === "ANALYST"}
            />
          </div>
        )}

        {!error && queueRows !== null && queueRows.length === 0 && (
          <div className="border border-[var(--color-rule)] p-6 text-[13px] text-[var(--color-text-muted)]">
            No cases require review right now.
          </div>
        )}

        {!error && queueRows !== null && queueRows.length > 0 && <QueueTable cases={queueRows} />}
      </div>
    </div>
  );
}
