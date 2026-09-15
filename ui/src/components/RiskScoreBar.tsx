/** Linear risk-score position against the real LOW/MEDIUM/HIGH thresholds
 * (shared/detection/model.py: LOW_RISK_THRESHOLD=0.40, HIGH_RISK_THRESHOLD=0.75).
 * A flat bar, not a circular gauge -- design spec S4/S9: no decorative dials. */
export function RiskScoreBar({ score }: { score: string }) {
  const value = Math.max(0, Math.min(1, parseFloat(score)));
  const pct = value * 100;
  return (
    <div>
      <div className="relative h-2 w-full overflow-hidden rounded-[2px] bg-[var(--color-surface-raised)]">
        <div className="absolute inset-y-0 left-0 bg-[var(--color-critical)]" style={{ width: "100%" }} />
        <div
          className="absolute inset-y-0 left-0 bg-[var(--color-caution)]"
          style={{ width: "75%" }}
        />
        <div className="absolute inset-y-0 left-0 bg-[var(--color-stable)]" style={{ width: "40%" }} />
        <div
          className="absolute top-[-2px] h-[12px] w-[2px] bg-[var(--color-text)]"
          style={{ left: `calc(${pct}% - 1px)` }}
          aria-hidden="true"
        />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-[var(--color-text-faint)]">
        <span>Low</span>
        <span>Medium</span>
        <span>High</span>
      </div>
      <div className="mt-0.5 font-mono text-[12px] text-[var(--color-text-muted)]" aria-label={`Risk score ${score}`}>
        score {score}
      </div>
    </div>
  );
}
