import { PenGlyph } from "./icons";
import { useAnalystIdentity } from "../lib/analystIdentity";
import { formatTimestamp } from "../lib/format";
import type { CaseDocument } from "../lib/types";

/** Finalized case: read-only decision record, not disabled buttons
 * (design spec #15) -- the human panel is replaced entirely.
 *
 * The caller viewing a FINALIZED case is, by the same ownership rule GET
 * /cases/{case_id} always enforces, necessarily the analyst who finalized
 * it -- assigned_analyst_id never changes after finalization, and access is
 * always scoped to assigned_analyst_id === caller.uid. So the server-
 * resolved caller identity (already available via the existing
 * X-Analyst-Display-Name header, the same one AnalystNavBar shows) is used
 * here instead of the raw Firebase UID -- no new data source, no UID ever
 * rendered.
 *
 * BLOCK_HOLD is shown in red, CLEAR in teal, matching the same accent used
 * on the decision button, the confirmation screen, and the dashboard.
 */
export function DecisionRecord({ caseDoc }: { caseDoc: CaseDocument }) {
  const identity = useAnalystIdentity();
  const isBlockHold = caseDoc.final_disposition === "BLOCK_HOLD";
  const accentColor = isBlockHold ? "var(--color-critical)" : "var(--color-stable)";

  return (
    <section className="p-4">
      <header className="mb-3 flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
        <PenGlyph />
        <span>Human decision</span>
        <span className="text-[var(--color-text-faint)]">&middot; Final authority</span>
      </header>
      <div className="border border-[var(--color-rule-strong)] p-3">
        <div className="text-[13px] text-[var(--color-text)]">
          {identity ? identity.displayName : "This analyst"} recorded:{" "}
          <span className="font-mono" style={{ color: accentColor }}>
            {caseDoc.final_disposition}
          </span>
        </div>
        <div className="mt-1 text-[12px] text-[var(--color-text-faint)]">
          {formatTimestamp(caseDoc.updated_at)}
        </div>
      </div>
    </section>
  );
}
