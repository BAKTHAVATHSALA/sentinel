import { useState } from "react";
import { PolicyGlyph } from "./icons";
import { DisclosureToggle } from "./DisclosureToggle";
import type { PolicyDecision } from "../lib/types";

/**
 * Policy: automated decision authority (design spec #8). Compact by default
 * (progressive disclosure): outcome label + one plain-English sentence.
 * Technical details (rule_id, rule_version, exact reasons, hard-risk tags
 * from inputs_snapshot) are behind an expand toggle -- nothing removed, just
 * deferred.
 *
 * Semantic color fix: ESCALATE is a SUCCESSFUL policy result routing the
 * case to a human -- amber (awaiting), never red. Red stays reserved for
 * genuine failures elsewhere on this page (e.g. ReasoningFailedNotice).
 */
export function PolicyLedgerEntry({ decision }: { decision: PolicyDecision }) {
  const [expanded, setExpanded] = useState(false);
  const escalate = decision.outcome === "ESCALATE";
  const outcomeLabel = escalate ? "HUMAN REVIEW" : "AUTO-RESOLVED";
  const outcomeColor = escalate ? "var(--color-caution)" : "var(--color-stable)";
  const plainEnglish = escalate ? "Human investigation required." : "No analyst action required.";

  const hardRiskTags = decision.inputs_snapshot?.hard_risk_tags_present;
  const hardRiskTagsList = Array.isArray(hardRiskTags) ? hardRiskTags : [];

  return (
    <section className="border-b border-[var(--color-rule)]">
      <header className="flex items-center gap-2 px-4 pt-4 text-[12px] text-[var(--color-text-muted)]">
        <PolicyGlyph />
        <span>Policy</span>
        <span className="text-[var(--color-text-faint)]">&middot; Automated decision</span>
      </header>
      <div className="mx-4 my-3 flex border" style={{ borderColor: "var(--color-rule-strong)" }}>
        <div className="w-1" style={{ backgroundColor: outcomeColor }} aria-hidden="true" />
        <div className="flex-1 p-3">
          <div className="flex items-center justify-between">
            <span className="text-[14px]" style={{ color: outcomeColor }}>
              {outcomeLabel}
            </span>
            <DisclosureToggle expanded={expanded} onToggle={() => setExpanded((e) => !e)} expandLabel="Policy details" collapseLabel="Hide policy details" />
          </div>
          <p className="mt-1 text-[13px] text-[var(--color-text)]">{plainEnglish}</p>

          {expanded && (
            <div className="mt-3 border-t border-dashed border-[var(--color-rule)] pt-3">
              <div className="font-mono text-[13px] text-[var(--color-text)]">
                {decision.rule_id} <span className="text-[var(--color-text-faint)]">v{decision.rule_version}</span>
              </div>
              <ul className="mt-2 flex flex-col gap-0.5">
                {decision.reasons.map((reason) => (
                  <li key={reason} className="text-[12px] text-[var(--color-text-muted)]">
                    {reason}
                  </li>
                ))}
              </ul>
              {hardRiskTagsList.length > 0 && (
                <p className="mt-2 text-[12px] text-[var(--color-caution)]">
                  Hard-risk tags: {hardRiskTagsList.join(", ")}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
