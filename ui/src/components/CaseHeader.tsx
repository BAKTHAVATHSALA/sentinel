import { AnomalyTagChip } from "./AnomalyTagChip";
import { RiskBadge } from "./StatusBadge";
import { formatMoney } from "../lib/format";
import type { CaseDocument } from "../lib/types";

/**
 * The compact, single-glance case header (progressive-disclosure PART 1):
 * state, actual risk, amount/merchant, and anomaly signals -- everything an
 * analyst needs to orient in about 10 seconds, before any evidence or
 * reasoning text. Transaction metadata (device/location/card/channel) that
 * used to occupy a full-height left sidebar (CaseSpine) is kept, just
 * demoted to a compact secondary row beneath the primary line -- nothing
 * removed, only reordered by importance.
 *
 * Semantic color rule (do not use red for a successful ESCALATE/HUMAN_REVIEW
 * outcome): HUMAN_REVIEW is amber (awaiting a decision, not a failure);
 * FINALIZED is red only when the actual recorded decision was BLOCK_HOLD,
 * otherwise teal; AUTO_RESOLVED is teal (informational/completed).
 */
export function CaseHeader({ caseDoc }: { caseDoc: CaseDocument }) {
  const { transaction, detection } = caseDoc;
  const stateLabel = caseDoc.state.replace(/_/g, " ");
  const stateColor =
    caseDoc.state === "HUMAN_REVIEW"
      ? "text-[var(--color-caution)]"
      : caseDoc.state === "FINALIZED" && caseDoc.final_disposition === "BLOCK_HOLD"
        ? "text-[var(--color-critical)]"
        : "text-[var(--color-stable)]";

  return (
    <div className="border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className={`text-[16px] tracking-tight ${stateColor}`}>{stateLabel}</span>
          <span className="font-mono text-[12px] text-[var(--color-text-faint)]">{caseDoc.case_id}</span>
        </div>
        <RiskBadge band={detection.risk_band} />
      </div>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="font-mono text-[22px] text-[var(--color-text)]">
          {formatMoney(transaction.amount, transaction.currency)}
        </span>
        <span className="text-[13px] text-[var(--color-text-muted)]">{transaction.merchant_id}</span>
      </div>

      {detection.anomaly_tags.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {detection.anomaly_tags.map((tag) => (
            <AnomalyTagChip key={tag} tag={tag} />
          ))}
        </div>
      )}

      <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-[var(--color-rule)] pt-2 text-[11px]">
        <div className="flex gap-1.5">
          <dt className="text-[var(--color-text-faint)]">Device</dt>
          <dd className="font-mono text-[var(--color-text-muted)]">{transaction.device_id}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-[var(--color-text-faint)]">Location</dt>
          <dd className="text-[var(--color-text-muted)]">{transaction.geo.country}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-[var(--color-text-faint)]">Card</dt>
          <dd className="font-mono text-[var(--color-text-muted)]">&bull;&bull;&bull;{transaction.card_id.slice(-4)}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-[var(--color-text-faint)]">Channel</dt>
          <dd className="text-[var(--color-text-muted)]">{transaction.channel}</dd>
        </div>
      </dl>
    </div>
  );
}
