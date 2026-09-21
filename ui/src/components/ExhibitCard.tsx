import { Fragment, useEffect, useRef, useState } from "react";
import { ToolSourceIcon } from "./icons";
import { DisclosureToggle } from "./DisclosureToggle";
import { useCitationThread } from "./CitationThread";
import { deriveExhibitSummary } from "../lib/exhibitSummary";
import { formatFieldName, formatFieldValue, formatTimestamp } from "../lib/format";
import type { Fact } from "../lib/types";

const TOOL_LABELS: Record<string, string> = {
  get_device_history: "Device history",
  get_ip_geovelocity: "IP geovelocity",
  get_behavioral_baseline: "Behavioral baseline",
  get_linked_entities: "Linked entities",
  get_merchant_risk: "Merchant risk",
  get_mock_kyc_status: "KYC status",
};

/**
 * One Exhibit per Fact -- numbered for citation addressing (design spec
 * #3/#9), never a generic "evidence card". Collapsed by default
 * (progressive-disclosure PART "EVIDENCE"): shows only the exhibit number,
 * tool/type, VERIFIED/DERIVED quality, a concise real-data-derived
 * conclusion, and one key value. Expanding reveals the complete existing
 * evidence -- every field, source_record_id, both timestamps -- nothing
 * technical is ever removed, only deferred behind one click.
 */
export function ExhibitCard({ fact, index, excluded }: { fact: Fact; index: number; excluded?: boolean }) {
  const { registerExhibit, activeFactIds } = useCitationThread();
  const ref = useRef<HTMLDivElement>(null);
  const isActive = activeFactIds.includes(fact.fact_id);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    registerExhibit(fact.fact_id, ref.current);
    return () => registerExhibit(fact.fact_id, null);
  }, [fact.fact_id, registerExhibit]);

  const comparison = deriveComparison(fact);
  const summary = deriveExhibitSummary(fact);
  const toolLabel = TOOL_LABELS[fact.source_tool] ?? fact.source_tool;

  return (
    <div
      ref={ref}
      id={`exhibit-${fact.fact_id}`}
      className={`border p-3 transition-colors duration-150 ${
        excluded
          ? "border-dashed border-[var(--color-rule-strong)] opacity-50"
          : isActive
            ? "border-[var(--color-stable)] bg-[var(--color-surface-raised)]"
            : "border-[var(--color-rule)] bg-[var(--color-surface)]"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[12px] text-[var(--color-text-muted)]">
              Exhibit {String(index + 1).padStart(2, "0")}
            </span>
            <span className="flex items-center gap-1 text-[12px] text-[var(--color-text-muted)]">
              <ToolSourceIcon tool={fact.source_tool} />
              {toolLabel}
            </span>
            <span className="text-[11px] text-[var(--color-text-faint)]">{fact.quality}</span>
            {excluded && (
              <span className="rounded-[3px] border border-dashed border-[var(--color-rule-strong)] px-1.5 py-0.5 text-[11px] text-[var(--color-text-faint)]">
                Excluded from this re-check
              </span>
            )}
          </div>

          <p className="text-[13px] text-[var(--color-text)]">
            {summary?.conclusion ?? toolLabel}
            {summary?.keyValue && <span className="ml-2 text-[12px] text-[var(--color-text-muted)]">{summary.keyValue}</span>}
          </p>
        </div>

        <DisclosureToggle
          expanded={expanded}
          onToggle={() => setExpanded((e) => !e)}
          expandLabel="View evidence"
          collapseLabel="Hide evidence"
        />
      </div>

      {expanded && (
        <div className="mt-3 border-t border-dashed border-[var(--color-rule)] pt-3">
          <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-[12px]">
            {Object.entries(fact.value)
              .filter(([k]) => !k.startsWith("_"))
              .map(([key, value]) => (
                <Fragment key={key}>
                  <dt className="text-[var(--color-text-faint)]">{formatFieldName(key)}</dt>
                  <dd className="min-w-0 break-words font-mono text-[var(--color-text-muted)]">
                    {formatFieldValue(value)}
                  </dd>
                </Fragment>
              ))}
            <dt className="text-[var(--color-text-faint)]">source record id</dt>
            <dd className="min-w-0 break-words font-mono text-[var(--color-text-muted)]">
              {fact.source_record_id ?? "--"}
            </dd>
            <dt className="text-[var(--color-text-faint)]">observed at</dt>
            <dd className="min-w-0 break-words font-mono text-[var(--color-text-muted)]">
              {formatTimestamp(fact.observed_at)}
            </dd>
            <dt className="text-[var(--color-text-faint)]">retrieved at</dt>
            <dd className="min-w-0 break-words font-mono text-[var(--color-text-muted)]">
              {formatTimestamp(fact.retrieved_at)}
            </dd>
          </dl>

          {comparison && (
            <div className="mt-2">
              <div className="flex justify-between text-[11px] text-[var(--color-text-faint)]">
                <span>{comparison.leftLabel}</span>
                <span>{comparison.rightLabel}</span>
              </div>
              <div className="relative mt-0.5 h-1.5 w-full rounded-[2px] bg-[var(--color-surface-raised)]">
                <div
                  className="absolute inset-y-0 left-0 rounded-[2px] bg-[var(--color-caution)]"
                  style={{ width: `${comparison.pct}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function deriveComparison(fact: Fact): { leftLabel: string; rightLabel: string; pct: number } | null {
  const v = fact.value as Record<string, unknown>;
  if (typeof v.typical_amount === "string" && typeof v.amount_deviation !== "undefined") {
    const typical = parseFloat(v.typical_amount as string);
    const deviation = parseFloat(String(v.amount_deviation));
    if (!Number.isNaN(typical) && !Number.isNaN(deviation)) {
      const pct = Math.min(100, (deviation / (deviation + 2)) * 100);
      return { leftLabel: `typical ~$${typical.toFixed(0)}`, rightLabel: `deviation ${deviation.toFixed(1)}x`, pct };
    }
  }
  if (typeof v.distance_km === "string") {
    const distance = parseFloat(v.distance_km as string);
    if (!Number.isNaN(distance)) {
      const pct = Math.min(100, (distance / 5000) * 100);
      return { leftLabel: "home location", rightLabel: `${distance.toFixed(0)} km away`, pct };
    }
  }
  return null;
}
