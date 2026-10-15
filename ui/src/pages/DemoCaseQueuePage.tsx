import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDemoDashboardCases } from "../lib/demoApi";
import { DemoNavBar } from "../components/DemoNavBar";
import { DashboardMetricCards } from "../components/DashboardMetricCards";
import { QueueTable } from "../components/QueueTable";
import { CaseDetailError } from "../components/StateNotices";
import { computeDashboardMetrics } from "../lib/dashboardMetrics";
import type { QueueCaseSummary } from "../lib/types";

export function DemoCaseQueuePage() {
  const [cases, setCases] = useState<QueueCaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchDemoDashboardCases()
      .then((data) => {
        if (!cancelled) {
          setCases(data);
          setError(null);
        }
      })
      .catch((e: any) => {
        if (!cancelled) setError(e.message ?? "Could not load the demo queue.");
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const queueRows = cases?.filter((c) => c.state === "HUMAN_REVIEW") ?? null;

  return (
    <div className="flex h-screen flex-col">
      <DemoNavBar onResetComplete={() => setReloadToken((t) => t + 1)} />

      <div className="mx-auto w-full max-w-[1400px] px-6 py-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-[20px] text-[var(--color-text)]">Sentinel Demo Queue</h1>
            <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
              10 pre-seeded synthetic cases spanning robust fraud, fragile risk, partial evidence, LLM schema recovery, and human finalization.
            </p>
          </div>
          <Link
            to="/investigate"
            className="border border-[var(--color-rule)] px-2.5 py-1.5 text-[12px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            Transaction Console
          </Link>
        </div>

        {error && <CaseDetailError message={error} onRetry={() => setReloadToken((t) => t + 1)} />}

        {!error && cases === null && (
          <div className="text-[13px] text-[var(--color-text-faint)]">Loading demo queue...</div>
        )}

        {!error && cases !== null && (
          <div className="mb-5">
            <DashboardMetricCards
              metrics={computeDashboardMetrics(cases)}
              showEscalatedToSenior={false}
            />
          </div>
        )}

        {!error && queueRows !== null && queueRows.length === 0 && (
          <div className="border border-[var(--color-rule)] p-6 text-[13px] text-[var(--color-text-muted)]">
            All demo cases in this session have been decided. Click &ldquo;Reset Demo&rdquo; to restore the initial dataset.
          </div>
        )}

        {!error && queueRows !== null && queueRows.length > 0 && <QueueTable cases={queueRows} />}
      </div>
    </div>
  );
}
