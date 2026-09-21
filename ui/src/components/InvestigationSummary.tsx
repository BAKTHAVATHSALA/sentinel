import type { CaseFindings } from "../lib/types";

const RISK_LABELS: Record<string, string> = { LOW: "Low", MEDIUM: "Medium", HIGH: "High" };

/**
 * Progressive-disclosure PART 2: the "understand this case in 10 seconds"
 * section, shown before any raw evidence or the full Gemini narrative. Every
 * word here is either a fixed label around a real enum value (risk_assessment
 * -- the same "map enum to label" pattern already used throughout this
 * codebase: RiskBadge, ACTION_LABELS) or a verbatim real statement from
 * findings.supporting_factors/counter_factors/evidence_gaps. No new AI text
 * is generated here.
 *
 * Deliberately does NOT say "Gemini recommends <action>": Gemini's
 * risk_assessment/recommended_disposition are advisory input only, and the
 * deterministic Policy engine -- not Gemini -- controls automated routing
 * (Contracts §2.1/§2.2). A case can legitimately have Detection=HIGH,
 * Gemini's own risk_assessment=MEDIUM, and Policy=ESCALATE all at once;
 * phrasing this as a "recommendation" reads as if Gemini drove that
 * decision. "AI assessment · <band> · Advisory" names whose assessment this
 * is and marks it advisory without implying it chose the outcome.
 *
 * Renders nothing when there is no CaseFindings to summarize (investigation
 * skipped, or Reasoning failed) -- the existing EmptyInvestigationNotice /
 * ReasoningFailedNotice remain the single authoritative explanation for
 * those cases, so this never states a second, possibly-diverging story.
 */
export function InvestigationSummary({ findings }: { findings: CaseFindings }) {
  const riskLabel = RISK_LABELS[findings.risk_assessment] ?? findings.risk_assessment;

  return (
    <section className="border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
      <header className="mb-2 text-[12px] text-[var(--color-text-muted)]">Investigation summary</header>

      <p className="text-[13px] text-[var(--color-text)]">
        AI assessment &middot; <strong className="font-medium">{riskLabel}</strong>
        <span className="ml-1 text-[11px] text-[var(--color-text-faint)]">
          &middot; Advisory (not the policy decision)
        </span>
      </p>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <SummaryList title="Supporting factors" items={findings.supporting_factors.map((f) => f.statement)} />
        <SummaryList title="Counter-evidence" items={findings.counter_factors.map((f) => f.statement)} />
        <SummaryList title="Evidence gaps" items={findings.evidence_gaps} />
      </div>
    </section>
  );
}

function SummaryList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <div className="mb-1 text-[11px] text-[var(--color-text-faint)]">
        {title} {items.length > 0 && <span>({items.length})</span>}
      </div>
      {items.length === 0 ? (
        <p className="text-[12px] text-[var(--color-text-faint)]">None</p>
      ) : (
        <ul className="list-disc pl-4 text-[12px] text-[var(--color-text-muted)]">
          {items.map((item) => (
            <li key={item} className="leading-[1.4]">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
