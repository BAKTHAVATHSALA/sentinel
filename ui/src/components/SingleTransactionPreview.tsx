import { useState } from "react";
import type { Transaction } from "../lib/types";

/**
 * The single-transaction preview (build.md Section 8) shown after parsing,
 * before any investigation runs -- the operator reviews what was actually
 * extracted before committing to POST /transactions. No fabricated city
 * name: the frozen Transaction schema's geo object only has country, so
 * that's what's shown (never a geocoded guess from lat/lon).
 */
export function SingleTransactionPreview({
  transaction,
  onInvestigate,
  onReset,
}: {
  transaction: Transaction;
  onInvestigate: () => void;
  onReset: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex flex-col gap-4 border border-[var(--color-rule)] bg-[var(--color-surface)] p-5">
      <div>
        <h2 className="text-[13px] text-[var(--color-text-muted)]">TRANSACTION READY</h2>
        <p className="mt-1 text-[22px] text-[var(--color-text)]">
          {transaction.currency} {transaction.amount}
        </p>
        <p className="text-[13px] text-[var(--color-text-muted)]">{transaction.merchant_category}</p>
        <p className="text-[13px] text-[var(--color-text-muted)]">
          {transaction.channel} &middot; {transaction.authorization_stage}
        </p>
        <p className="text-[13px] text-[var(--color-text-muted)]">{transaction.geo.country}</p>
      </div>

      <div className="grid grid-cols-3 gap-4 text-[12px]">
        <div>
          <p className="text-[var(--color-text-faint)]">Transaction ID</p>
          <p className="font-mono text-[var(--color-text)]">{transaction.transaction_id}</p>
        </div>
        <div>
          <p className="text-[var(--color-text-faint)]">Customer</p>
          <p className="font-mono text-[var(--color-text)]">{transaction.customer_id}</p>
        </div>
        <div>
          <p className="text-[var(--color-text-faint)]">Device</p>
          <p className="font-mono text-[var(--color-text)]">{transaction.device_id}</p>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="self-start text-[12px] text-[var(--color-text-muted)] underline"
      >
        {expanded ? "Hide transaction details" : "View transaction details"}
      </button>

      {expanded && (
        <div className="grid grid-cols-2 gap-2 border-t border-[var(--color-rule)] pt-3 text-[12px] sm:grid-cols-3">
          {Object.entries({
            account_id: transaction.account_id,
            card_id: transaction.card_id,
            merchant_id: transaction.merchant_id,
            ip_address: transaction.ip_address,
            geo_lat: transaction.geo.lat,
            geo_lon: transaction.geo.lon,
            card_present: String(transaction.card_present),
            timestamp: transaction.timestamp,
          }).map(([key, value]) => (
            <div key={key}>
              <p className="text-[var(--color-text-faint)]">{key}</p>
              <p className="font-mono text-[var(--color-text)]">{value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onInvestigate}
          className="border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-4 py-2 text-[13px] text-[var(--color-text)]"
        >
          Investigate Transaction
        </button>
        <button type="button" onClick={onReset} className="border border-[var(--color-rule)] px-3 py-2 text-[13px] text-[var(--color-text-muted)]">
          Upload a different file
        </button>
      </div>
    </div>
  );
}
