/** Formatting helpers. Amounts/scores are rendered directly from the
 * backend's decimal strings -- never parsed to float and reformatted --
 * so the displayed value is exactly what the ledger recorded. */

export function formatMoney(amount: string, currency: string): string {
  const symbol = currency === "USD" ? "$" : `${currency} `;
  return `${symbol}${amount}`;
}

export function formatAge(isoTimestamp: string): string {
  const then = new Date(isoTimestamp).getTime();
  const now = Date.now();
  const totalMinutes = Math.max(0, Math.floor((now - then) / 60000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

export function formatTimestamp(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatFieldName(key: string): string {
  return key.replace(/_/g, " ");
}

export function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) return "--";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
