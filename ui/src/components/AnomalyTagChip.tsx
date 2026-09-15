import type { AnomalyTag } from "../lib/types";

const TAG_LABELS: Record<string, string> = {
  NEW_DEVICE: "New device",
  UNUSUAL_LOCATION: "Unusual location",
  UNUSUAL_AMOUNT: "Unusual amount",
  MERCHANT_RISK: "Merchant risk",
  LINKED_ENTITY_ANOMALY: "Linked entity",
  KYC_ANOMALY: "KYC anomaly",
  IMPOSSIBLE_TRAVEL: "Impossible travel",
  UNUSUAL_TIME: "Unusual time",
};

export function AnomalyTagChip({ tag }: { tag: AnomalyTag }) {
  return (
    <span className="inline-block rounded-[3px] border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-2 py-0.5 text-[12px] text-[var(--color-text-muted)]">
      {TAG_LABELS[tag] ?? tag}
    </span>
  );
}
