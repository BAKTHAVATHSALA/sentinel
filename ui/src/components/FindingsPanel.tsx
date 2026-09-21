import { useState } from "react";
import { CitationChip } from "./CitationChip";
import { DisclosureToggle } from "./DisclosureToggle";
import { CompassGlyph } from "./icons";
import type { CaseFindings, FindingFactor } from "../lib/types";

/**
 * Gemini's assessment -- explicitly advisory, never a decision (design
 * spec #8/D). Progressive disclosure: Supporting/Counter/Evidence gaps stay
 * visible by default (they're short, structured, and already summarized
 * again at the top of the page by InvestigationSummary); the full narrative
 * paragraph -- the long free-text an analyst doesn't need to read to
 * understand the case -- is collapsed by default and expands on demand.
 * The Gemini output itself is never modified, only when it's shown.
 */
export function FindingsPanel({
  findings,
  exhibitNumbers,
}: {
  findings: CaseFindings;
  exhibitNumbers: Record<string, number>;
}) {
  const [narrativeExpanded, setNarrativeExpanded] = useState(false);

  return (
    <section className="border-t border-[var(--color-rule)] bg-[var(--color-surface-reading)] p-4">
      <header className="mb-3 flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
        <CompassGlyph />
        <span>Gemini's assessment</span>
        <span className="text-[var(--color-text-faint)]">&middot; Advisory, not a decision</span>
      </header>

      <div className="flex items-start justify-between gap-3">
        <p className="text-[12px] text-[var(--color-text-faint)]">Full narrative assessment</p>
        <DisclosureToggle
          expanded={narrativeExpanded}
          onToggle={() => setNarrativeExpanded((e) => !e)}
          expandLabel="Show full assessment"
          collapseLabel="Hide full assessment"
        />
      </div>
      {narrativeExpanded && (
        <p className="mt-2 max-w-[68ch] text-[15px] leading-[1.55] text-[var(--color-text)]">
          {findings.summary}
        </p>
      )}

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
            <span className="max-w-[46ch] leading-[1.5]">{factor.statement}</span>
            <CitationChip factIds={factor.fact_ids} exhibitNumbers={exhibitNumbers} />
          </li>
        ))}
      </ul>
    </div>
  );
}
