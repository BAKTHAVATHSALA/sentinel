import type { CaseDashboardMetrics } from "../lib/dashboardMetrics";

/**
 * Visually secondary metric strip above the case queue table -- plain counts
 * only, reusing the same stat-tile style already established for the public
 * Transaction Console's batch results (BatchInvestigationView.tsx): a bordered
 * tile with a large number and a small muted label, no icons forced onto them
 * (this project's icon set is domain-specific glyphs -- risk band, robustness
 * pillars -- none of which mean anything generic enough for "count of cases"),
 * no charts, no percentages, no trend arrows. Zero renders as "0", never "--".
 */
export function DashboardMetricCards({
  metrics,
  showEscalatedToSenior,
}: {
  metrics: CaseDashboardMetrics;
  showEscalatedToSenior: boolean;
}) {
  const cards: { label: string; value: number; style: string }[] = [
    { label: "Total Cases", value: metrics.totalCases, style: "text-[var(--color-text)]" },
    { label: "Open Cases", value: metrics.openCases, style: "text-[var(--color-caution)]" },
    { label: "Closed Cases", value: metrics.closedCases, style: "text-[var(--color-stable)]" },
    { label: "Block & Hold", value: metrics.blockHoldCases, style: "text-[var(--color-critical)]" },
  ];
  if (showEscalatedToSenior) {
    cards.push({ label: "Escalated to Senior", value: metrics.escalatedToSenior, style: "text-[var(--color-text-muted)]" });
  }

  // Tailwind's class scanner needs literal class strings, not interpolated
  // ones -- `sm:grid-cols-${n}` would never be generated.
  const gridColsClass = showEscalatedToSenior ? "sm:grid-cols-5" : "sm:grid-cols-4";

  return (
    <div className={`grid grid-cols-2 gap-3 ${gridColsClass}`} aria-label="Case metrics">
      {cards.map((card) => (
        <div
          key={card.label}
          data-testid={`dashboard-metric-${card.label}`}
          className="border border-[var(--color-rule)] bg-[var(--color-surface)] p-3 text-center"
        >
          <p className={`text-[20px] ${card.style}`}>{card.value}</p>
          <p className="text-[11px] text-[var(--color-text-muted)]">{card.label}</p>
        </div>
      ))}
    </div>
  );
}
