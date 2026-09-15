import { CompassGlyph } from "./icons";
import { SupportPillars } from "./SupportPillars";
import type { CaseFindings, RobustnessResult } from "../lib/types";

/**
 * Robustness / counterfactual panel (design spec #10, signature interaction
 * #2). The fast-path estimate is real data from the case document. The live
 * counterfactual re-check has no authorized backend endpoint yet (Contracts
 * S23.1 / Build Checklist 5.1 list exactly POST /transactions, GET /cases,
 * GET /cases/{case_id}, POST /cases/{case_id}/decision -- no counterfactual
 * trigger) -- rather than invent one, this is shown as unavailable, honestly.
 */
export function CounterfactualPanel({
  robustness,
  findings,
  exhibitNumbers,
}: {
  robustness: RobustnessResult | null;
  findings: CaseFindings | null;
  exhibitNumbers: Record<string, number>;
}) {
  return (
    <section className="border-b border-[var(--color-rule)] p-4">
      <header className="mb-3 flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
        <CompassGlyph />
        <span>Robustness</span>
        <span className="text-[var(--color-text-faint)]">&middot; Advisory</span>
      </header>

      {robustness && findings ? (
        <SupportPillars robustness={robustness} findings={findings} exhibitNumbers={exhibitNumbers} />
      ) : (
        <p className="text-[12px] text-[var(--color-text-faint)]">Not scored -- no findings to evaluate.</p>
      )}

      <div className="mt-3 border-t border-dashed border-[var(--color-rule)] pt-3">
        <p className="text-[11px] text-[var(--color-text-faint)]">
          Live re-check is not available for this case yet. The estimate above is the fast-path result only.
        </p>
      </div>
    </section>
  );
}
