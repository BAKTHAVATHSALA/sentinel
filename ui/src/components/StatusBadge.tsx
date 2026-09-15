import { EvidenceQualityGlyph, PillarsGlyph, RiskGlyph } from "./icons";
import type { EvidenceCompleteness, RiskBand, RobustnessClassification } from "../lib/types";

/**
 * Status is never color alone (WCAG 2.1 AA, design spec S9/S14): every
 * badge pairs its color token with a shape glyph and a text label.
 */

const RISK_STYLES: Record<RiskBand, string> = {
  LOW: "text-[var(--color-stable)] bg-[var(--color-stable-soft)]",
  MEDIUM: "text-[var(--color-caution)] bg-[var(--color-caution-soft)]",
  HIGH: "text-[var(--color-critical)] bg-[var(--color-critical-soft)]",
};

export function RiskBadge({ band }: { band: RiskBand }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-[3px] px-2 py-0.5 text-[13px] ${RISK_STYLES[band]}`}>
      <RiskGlyph band={band} />
      {band === "LOW" ? "Low" : band === "MEDIUM" ? "Medium" : "High"}
    </span>
  );
}

export function RobustnessBadge({
  classification,
  supportingCount,
}: {
  classification: RobustnessClassification;
  supportingCount: number;
}) {
  const fragile = classification === "FRAGILE";
  const style = fragile
    ? "text-[var(--color-caution)] bg-[var(--color-caution-soft)]"
    : "text-[var(--color-stable)] bg-[var(--color-stable-soft)]";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-[3px] px-2 py-0.5 text-[13px] ${style}`}>
      <PillarsGlyph count={supportingCount} fragile={fragile} />
      {fragile ? "Fragile" : "Robust"}
    </span>
  );
}

export function EvidenceCompletenessBadge({ completeness }: { completeness: EvidenceCompleteness }) {
  const complete = completeness === "COMPLETE";
  const style = complete
    ? "text-[var(--color-stable)] bg-[var(--color-stable-soft)]"
    : "text-[var(--color-caution)] bg-[var(--color-caution-soft)]";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-[3px] px-2 py-0.5 text-[13px] ${style}`}>
      <EvidenceQualityGlyph complete={complete} />
      {complete ? "Complete" : "Partial"}
    </span>
  );
}
