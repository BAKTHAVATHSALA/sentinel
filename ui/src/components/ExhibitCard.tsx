import { Fragment, useEffect, useRef } from "react";
import { ToolSourceIcon } from "./icons";
import { useCitationThread } from "./CitationThread";
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

/** One Exhibit per Fact -- numbered for citation addressing (design spec
 * #3/#9), never a generic "evidence card". Real amount/typical-amount and
 * distance/elapsed-time comparisons render as small literal bars, not
 * decorative charts. */
export function ExhibitCard({ fact, index, excluded }: { fact: Fact; index: number; excluded?: boolean }) {
  const { registerExhibit, activeFactIds } = useCitationThread();
  const ref = useRef<HTMLDivElement>(null);
  const isActive = activeFactIds.includes(fact.fact_id);

  useEffect(() => {
    registerExhibit(fact.fact_id, ref.current);
    return () => registerExhibit(fact.fact_id, null);
  }, [fact.fact_id, registerExhibit]);

  const comparison = deriveComparison(fact);

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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[12px] text-[var(--color-text-muted)]">
            Exhibit {String(index + 1).padStart(2, "0")}
          </span>
          <span className="flex items-center gap-1 text-[12px] text-[var(--color-text-muted)]">
            <ToolSourceIcon tool={fact.source_tool} />
            {TOOL_LABELS[fact.source_tool] ?? fact.source_tool}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {excluded && (
            <span className="rounded-[3px] border border-dashed border-[var(--color-rule-strong)] px-1.5 py-0.5 text-[11px] text-[var(--color-text-faint)]">
              Excluded from this re-check
            </span>
          )}
          <span className="text-[11px] text-[var(--color-text-faint)]">{fact.quality}</span>
        </div>
      </div>

      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-[12px]">
        {Object.entries(fact.value)
          .filter(([k]) => !k.startsWith("_"))
          .slice(0, 6)
          .map(([key, value]) => (
            <Fragment key={key}>
              <dt className="text-[var(--color-text-faint)]">{formatFieldName(key)}</dt>
              <dd className="min-w-0 break-words font-mono text-[var(--color-text-muted)]">
                {formatFieldValue(value)}
              </dd>
            </Fragment>
          ))}
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

      <div className="mt-2 text-[11px] text-[var(--color-text-faint)]">observed {formatTimestamp(fact.observed_at)}</div>
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
