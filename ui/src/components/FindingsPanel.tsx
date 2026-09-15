import { CitationChip } from "./CitationChip";
import { CompassGlyph } from "./icons";
import type { CaseFindings, FindingFactor } from "../lib/types";

/**
 * Gemini's assessment -- explicitly advisory, never a decision (design
 * spec #8/D). Serif narrative register (design spec #5): reads as authored
 * prose, distinct from the mono data register and the sans UI chrome.
 */
export function FindingsPanel({
  findings,
  exhibitNumbers,
}: {
  findings: CaseFindings;
  exhibitNumbers: Record<string, number>;
}) {
  return (
    <section className="border-t border-[var(--color-rule)] bg-[var(--color-surface-reading)] p-4">
      <header className="mb-3 flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
        <CompassGlyph />
        <span>Gemini's assessment</span>
        <span className="text-[var(--color-text-faint)]">&middot; Advisory, not a decision</span>
      </header>

      <p className="max-w-[68ch] font-serif text-[15px] leading-[1.55] text-[var(--color-text)]">
        {findings.summary}
      </p>

      {findings.supporting_factors.length > 0 && (
        <FactorGroup title="Supporting" factors={findings.supporting_factors} exhibitNumbers={exhibitNumbers} />
      )}
      {findings.counter_factors.length > 0 && (
        <FactorGroup title="Counter" factors={findings.counter_factors} exhibitNumbers={exhibitNumbers} />
      )}

      {findings.evidence_gaps.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-[12px] text-[var(--color-text-faint)]">Evidence gaps</div>
          <ul className="list-disc pl-5 text-[13px] text-[var(--color-text-muted)]">
            {findings.evidence_gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function FactorGroup({
  title,
  factors,
  exhibitNumbers,
}: {
  title: string;
  factors: FindingFactor[];
  exhibitNumbers: Record<string, number>;
}) {
  return (
    <div className="mt-3">
      <div className="mb-1.5 text-[12px] text-[var(--color-text-faint)]">{title}</div>
      <ul className="flex flex-col gap-2">
        {factors.map((factor) => (
          <li key={factor.statement} className="flex flex-wrap items-start gap-2 text-[13px] text-[var(--color-text-muted)]">
            <span className="rounded-[3px] border border-[var(--color-rule-strong)] px-1.5 py-0.5 text-[11px] text-[var(--color-text-faint)]">
              {factor.materiality}
            </span>
            <span className="max-w-[46ch] font-serif leading-[1.5]">{factor.statement}</span>
            <CitationChip factIds={factor.fact_ids} exhibitNumbers={exhibitNumbers} />
          </li>
        ))}
      </ul>
    </div>
  );
}
