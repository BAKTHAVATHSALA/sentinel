import { useState } from "react";
import { PillarsGlyph } from "./icons";
import { DisclosureToggle } from "./DisclosureToggle";
import { CitationChip } from "./CitationChip";
import type { CaseFindings, RobustnessResult } from "../lib/types";

const COMPACT_SUMMARY: Record<"ROBUST" | "FRAGILE", string> = {
  ROBUST: "Assessment remains supported when individual evidence factors are removed.",
  FRAGILE: "Assessment would not survive removing a single evidence factor.",
};

/**
 * "Support Pillars" -- not a fake confidence percentage (Contracts:
 * Gemini's risk_assessment is never a calibrated probability). Renders
 * exactly what shared/robustness/scorer.py's fast_path() computed: one
 * pillar per HIGH-materiality supporting factor. 2+ = ROBUST, 1 = FRAGILE.
 *
 * Compact by default (progressive disclosure): the classification badge and
 * one fixed sentence describing what ROBUST/FRAGILE means are always
 * visible; the detailed factor-count explanation, the fragile-factor
 * citation, and the "fast-path estimate" provenance note are behind an
 * expand toggle.
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
  const [expanded, setExpanded] = useState(false);
  const highFactors = findings.supporting_factors.filter((f) => f.materiality === "HIGH");
  const fragile = robustness.classification === "FRAGILE";

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <PillarsGlyph count={highFactors.length} fragile={fragile} className="text-[var(--color-text)]" />
          <span className={fragile ? "text-[var(--color-caution)]" : "text-[var(--color-stable)]"}>
            {fragile ? "Fragile" : "Robust"}
          </span>
          <span className="rounded-[3px] border border-[var(--color-rule-strong)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-faint)]">
            Fast-path
          </span>
        </div>
        <DisclosureToggle expanded={expanded} onToggle={() => setExpanded((e) => !e)} expandLabel="Details" collapseLabel="Hide details" />
      </div>

      <p className="mt-1.5 text-[12px] text-[var(--color-text-muted)]">{COMPACT_SUMMARY[fragile ? "FRAGILE" : "ROBUST"]}</p>

      {expanded && (
        <div className="mt-2 border-t border-dashed border-[var(--color-rule)] pt-2">
          <p className="text-[12px] text-[var(--color-text-muted)]">
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
      )}
    </div>
  );
}
