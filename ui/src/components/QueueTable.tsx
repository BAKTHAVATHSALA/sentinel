import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { RiskBadge, RobustnessBadge } from "./StatusBadge";
import { AnomalyTagChip } from "./AnomalyTagChip";
import { formatAge, formatMoney } from "../lib/format";
import type { QueueCaseSummary, RiskBand, RobustnessClassification } from "../lib/types";

const RISK_ORDER: Record<RiskBand, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };
const SLA_BREACH_MINUTES = 120;

type RiskFilter = "ALL" | RiskBand;
type RobustnessFilter = "ALL" | RobustnessClassification;

/** Dense triage table (design spec B) -- risk and robustness lead the
 * scanning order because they decide "open this one next"; why-flagged
 * follows so an analyst can pattern-match without opening the case. */
export function QueueTable({ cases }: { cases: QueueCaseSummary[] }) {
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("ALL");
  const [robustnessFilter, setRobustnessFilter] = useState<RobustnessFilter>("ALL");

  const filtered = useMemo(() => {
    return cases
      .filter((c) => riskFilter === "ALL" || c.risk_band === riskFilter)
      .filter((c) => robustnessFilter === "ALL" || c.robustness_classification === robustnessFilter)
      .sort((a, b) => RISK_ORDER[a.risk_band] - RISK_ORDER[b.risk_band]);
  }, [cases, riskFilter, robustnessFilter]);

  return (
    <div>
      <div className="mb-3 flex items-center gap-3 text-[13px] text-[var(--color-text-muted)]">
        <span>{cases.length} open</span>
        <FilterSelect
          label="Risk"
          value={riskFilter}
          onChange={setRiskFilter}
          options={["ALL", "HIGH", "MEDIUM", "LOW"]}
        />
        <FilterSelect
          label="Robustness"
          value={robustnessFilter}
          onChange={setRobustnessFilter}
          options={["ALL", "FRAGILE", "ROBUST"]}
        />
      </div>

      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-[var(--color-rule)] text-left text-[12px] text-[var(--color-text-faint)]">
            <th className="w-1"></th>
            <th className="py-2 pr-3 font-normal">Risk</th>
            <th className="py-2 pr-3 font-normal">Robustness</th>
            <th className="py-2 pr-3 font-normal">Why flagged</th>
            <th className="py-2 pr-3 text-right font-normal">Amount</th>
            <th className="py-2 pr-3 font-normal">Merchant</th>
            <th className="py-2 pr-3 font-normal">State</th>
            <th className="py-2 pr-3 text-right font-normal">Age</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((c) => {
            const breach = minutesSince(c.created_at) >= SLA_BREACH_MINUTES;
            return (
              <tr key={c.case_id} className="border-b border-[var(--color-rule)] hover:bg-[var(--color-surface)]">
                <td>
                  <div
                    className="h-full w-[3px]"
                    style={{ backgroundColor: breach ? "var(--color-critical)" : "transparent" }}
                    aria-label={breach ? "SLA breached" : undefined}
                  />
                </td>
                <td className="py-2 pr-3">
                  <Link
                    to={c.case_id.startsWith("demo_") ? `/demo/case/${encodeURIComponent(c.case_id)}` : `/case/${c.case_id}`}
                    className="focus-visible:outline focus-visible:outline-2"
                  >
                    <RiskBadge band={c.risk_band} />
                  </Link>
                </td>
                <td className="py-2 pr-3">
                  {c.robustness_classification ? (
                    // QueueCaseSummary carries only the classification, not the real
                    // high-materiality factor count (that lives on CaseFindings, fetched
                    // only on the case detail page) -- 2/1 is the glyph's minimum pillar
                    // count for ROBUST/FRAGILE respectively, a legible approximation for
                    // this dense row, not a claim about the real factor count.
                    <RobustnessBadge classification={c.robustness_classification} supportingCount={c.robustness_classification === "ROBUST" ? 2 : 1} />
                  ) : (
                    <span className="text-[12px] text-[var(--color-text-faint)]">not scored</span>
                  )}
                </td>
                <td className="py-2 pr-3">
                  <div className="flex flex-wrap gap-1">
                    {c.anomaly_tags.slice(0, 2).map((tag) => (
                      <AnomalyTagChip key={tag} tag={tag} />
                    ))}
                    {c.anomaly_tags.length > 2 && (
                      <span className="text-[11px] text-[var(--color-text-faint)]">+{c.anomaly_tags.length - 2}</span>
                    )}
                  </div>
                </td>
                <td className="py-2 pr-3 text-right font-mono">{formatMoney(c.amount, c.currency)}</td>
                <td className="py-2 pr-3 text-[var(--color-text-muted)]">{c.merchant_id}</td>
                <td className="py-2 pr-3 text-[var(--color-text-muted)]">{c.state.replace(/_/g, " ")}</td>
                <td className="py-2 pr-3 text-right font-mono text-[var(--color-text-muted)]">{formatAge(c.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {filtered.length === 0 && (
        <div className="p-6 text-[13px] text-[var(--color-text-faint)]">No cases match these filters.</div>
      )}
    </div>
  );
}

function minutesSince(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
}

function FilterSelect<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: T[];
}) {
  return (
    <label className="flex items-center gap-1.5">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="border border-[var(--color-rule)] bg-[var(--color-surface)] px-1.5 py-0.5 text-[var(--color-text)]"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt === "ALL" ? "All" : opt.charAt(0) + opt.slice(1).toLowerCase()}
          </option>
        ))}
      </select>
    </label>
  );
}
