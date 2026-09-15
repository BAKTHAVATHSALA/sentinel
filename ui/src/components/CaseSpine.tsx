import { AnomalyTagChip } from "./AnomalyTagChip";
import { RiskBadge } from "./StatusBadge";
import { RiskScoreBar } from "./RiskScoreBar";
import { formatMoney } from "../lib/format";
import type { CaseDocument } from "../lib/types";

export function CaseSpine({ caseDoc }: { caseDoc: CaseDocument }) {
  const { transaction, detection } = caseDoc;
  return (
    <div className="flex w-[260px] min-w-[260px] max-w-[300px] flex-col gap-4 border-r border-[var(--color-rule)] p-4">
      <div>
        <div className="font-mono text-[12px] text-[var(--color-text-muted)]">{caseDoc.case_id}</div>
        <div className="mt-0.5 text-[13px] text-[var(--color-text)]">{caseDoc.state.replace(/_/g, " ")}</div>
      </div>

      <div>
        <div className="font-mono text-[24px] text-[var(--color-text)]">
          {formatMoney(transaction.amount, transaction.currency)}
        </div>
        <div className="text-[13px] text-[var(--color-text-muted)]">{transaction.merchant_id}</div>
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-[12px]">
        <dt className="text-[var(--color-text-faint)]">Device</dt>
        <dd className="font-mono text-[var(--color-text-muted)]">{transaction.device_id}</dd>
        <dt className="text-[var(--color-text-faint)]">Location</dt>
        <dd className="text-[var(--color-text-muted)]">{transaction.geo.country}</dd>
        <dt className="text-[var(--color-text-faint)]">Card</dt>
        <dd className="font-mono text-[var(--color-text-muted)]">
          &bull;&bull;&bull;{transaction.card_id.slice(-4)}
        </dd>
        <dt className="text-[var(--color-text-faint)]">Channel</dt>
        <dd className="text-[var(--color-text-muted)]">{transaction.channel}</dd>
      </dl>

      <div>
        <RiskBadge band={detection.risk_band} />
        <div className="mt-2">
          <RiskScoreBar score={detection.risk_score} />
        </div>
      </div>

      {detection.anomaly_tags.length > 0 && (
        <div>
          <div className="mb-1.5 text-[12px] text-[var(--color-text-faint)]">Why flagged</div>
          <div className="flex flex-wrap gap-1.5">
            {detection.anomaly_tags.map((tag) => (
              <AnomalyTagChip key={tag} tag={tag} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
