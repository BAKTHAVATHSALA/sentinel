import { PillarsGlyph } from "./icons";
import { CitationChip } from "./CitationChip";
import type { CaseFindings, RobustnessResult } from "../lib/types";

/**
 * "Support Pillars" -- not a fake confidence percentage (Contracts:
 * Gemini's risk_assessment is never a calibrated probability). Renders
 * exactly what shared/robustness/scorer.py's fast_path() computed: one
 * pillar per HIGH-materiality supporting factor. 2+ = ROBUST, 1 = FRAGILE.
 */
export function SupportPillars({
  robustness,
  findings,
  exhibitNumbers,
}: {
  robustness: RobustnessResult;
  findings: CaseFindings;
  exhibitNumbers: Record<string, number>;
}) {
  const highFactors = findings.supporting_factors.filter((f) => f.materiality === "HIGH");
  const fragile = robustness.classification === "FRAGILE";

  return (
    <div>
      <div className="flex items-center gap-2">
        <PillarsGlyph count={highFactors.length} fragile={fragile} className="text-[var(--color-text)]" />
        <span className={fragile ? "text-[var(--color-caution)]" : "text-[var(--color-stable)]"}>
          {fragile ? "Fragile" : "Robust"}
        </span>
      </div>
      <p className="mt-1.5 text-[12px] text-[var(--color-text-muted)]">
        {highFactors.length} high-materiality {highFactors.length === 1 ? "factor" : "factors"} support this finding.
        {fragile
          ? " Removing the sole high-materiality factor would flip this finding below the escalation threshold."
          : " Removing any single one still leaves another supporting it."}
      </p>
      {fragile && robustness.fragile_factor_id && exhibitNumbers[robustness.fragile_factor_id] && (
        <p className="mt-1 text-[12px] text-[var(--color-caution)]">
          Fragile factor:{" "}
          <CitationChip factIds={[robustness.fragile_factor_id]} exhibitNumbers={exhibitNumbers} />
        </p>
      )}
      <p className="mt-2 text-[11px] text-[var(--color-text-faint)]">
        Fast-path estimate &middot; based on materiality, not a live re-check
      </p>
    </div>
  );
}
