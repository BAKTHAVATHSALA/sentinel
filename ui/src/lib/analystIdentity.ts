import { useSyncExternalStore } from "react";

/**
 * The currently authenticated analyst's server-resolved identity
 * (display_name/role), as populated from the X-Analyst-Display-Name /
 * X-Analyst-Role response headers that GET /cases and GET /cases/{case_id}
 * already additively return (see services/api/cases.py). This is NOT a
 * new endpoint and NOT a client-supplied value -- role is still only ever
 * resolved server-side; this module just makes that already-real value
 * available to the persistent nav bar without a dedicated "who am I" call.
 *
 * A tiny module-level store (not React Context) so lib/api.ts's plain
 * fetch helper can populate it as a side effect of any authenticated
 * request, without threading a callback through every call site.
 */

export interface AnalystIdentity {
  displayName: string;
  role: "ANALYST" | "SENIOR_ANALYST";
}

let currentIdentity: AnalystIdentity | null = null;
const listeners = new Set<() => void>();

export function setAnalystIdentity(identity: AnalystIdentity): void {
  currentIdentity = identity;
  listeners.forEach((listener) => listener());
}

export function clearAnalystIdentity(): void {
  currentIdentity = null;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): AnalystIdentity | null {
  return currentIdentity;
}

/** React hook: re-renders whenever the identity changes (e.g. once the
 * first authenticated response lands). Returns null until then. */
export function useAnalystIdentity(): AnalystIdentity | null {
  return useSyncExternalStore(subscribe, getSnapshot);
}
