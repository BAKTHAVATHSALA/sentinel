import { PenGlyph } from "./icons";
import { formatTimestamp } from "../lib/format";
import type { CaseDocument } from "../lib/types";

/** Finalized case: read-only decision record, not disabled buttons
 * (design spec #15) -- the human panel is replaced entirely. */
export function DecisionRecord({ caseDoc }: { caseDoc: CaseDocument }) {
  return (
    <section className="p-4">
      <header className="mb-3 flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
        <PenGlyph />
        <span>Human decision</span>
        <span className="text-[var(--color-text-faint)]">&middot; Final authority</span>
      </header>
      <div className="border border-[var(--color-rule-strong)] p-3">
        <div className="text-[13px] text-[var(--color-text)]">
          Analyst {caseDoc.assigned_analyst_id ?? "unknown"} recorded:{" "}
          <span className="font-mono">{caseDoc.final_disposition}</span>
        </div>
        <div className="mt-1 text-[12px] text-[var(--color-text-faint)]">
          {formatTimestamp(caseDoc.updated_at)}
        </div>
      </div>
    </section>
  );
}
