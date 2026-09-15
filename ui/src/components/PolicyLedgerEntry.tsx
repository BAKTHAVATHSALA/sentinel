import { PolicyGlyph } from "./icons";
import type { PolicyDecision } from "../lib/types";

/**
 * Policy: automated decision authority (design spec #8). Hard-edged,
 * mono rule_id/version, a single left-edge bar (not a full-color fill --
 * this is a record, not an alert) -- visually heavier than the Gemini
 * panel, never softened.
 */
export function PolicyLedgerEntry({ decision }: { decision: PolicyDecision }) {
  const escalate = decision.outcome === "ESCALATE";
  const barColor = escalate ? "var(--color-critical)" : "var(--color-stable)";

  return (
    <section className="border-b border-[var(--color-rule)]">
      <header className="flex items-center gap-2 px-4 pt-4 text-[12px] text-[var(--color-text-muted)]">
        <PolicyGlyph />
        <span>Policy</span>
        <span className="text-[var(--color-text-faint)]">&middot; Automated decision</span>
      </header>
      <div className="mx-4 my-3 flex border" style={{ borderColor: "var(--color-rule-strong)" }}>
        <div className="w-1" style={{ backgroundColor: barColor }} aria-hidden="true" />
        <div className="flex-1 p-3">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-[13px] text-[var(--color-text)]">
              {decision.rule_id} <span className="text-[var(--color-text-faint)]">v{decision.rule_version}</span>
            </span>
            <span className="text-[13px] text-[var(--color-text)]">{escalate ? "Escalate" : "Auto-resolve"}</span>
          </div>
          <ul className="mt-2 flex flex-col gap-0.5">
            {decision.reasons.map((reason) => (
              <li key={reason} className="text-[12px] text-[var(--color-text-muted)]">
                {reason}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
