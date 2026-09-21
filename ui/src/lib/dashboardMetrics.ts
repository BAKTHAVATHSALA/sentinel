import type { QueueCaseSummary } from "./types";

/**
 * Pure, deterministic derivation of the dashboard metric cards from the same
 * authorized case dataset the queue page already fetches (GET
 * /cases?scope=dashboard) -- no second source of truth, no separate fetch,
 * no invented numbers. Every count here is a straightforward filter over the
 * real rows the backend returned for this authenticated caller.
 *
 * Field semantics (see services/api/cases.py:list_cases):
 * - A row with `is_escalated_by_me: true` is a case this analyst escalated
 *   via ESCALATE_SENIOR; it is no longer assigned to them, so it counts
 *   toward `escalatedToSenior` only, never toward total/open/closed.
 * - Every other row is currently assigned to this caller (HUMAN_REVIEW or
 *   FINALIZED) and counts toward total, plus exactly one of open/closed.
 */
export interface CaseDashboardMetrics {
  totalCases: number;
  openCases: number;
  closedCases: number;
  blockHoldCases: number;
  escalatedToSenior: number;
}

export function computeDashboardMetrics(cases: QueueCaseSummary[]): CaseDashboardMetrics {
  const ownCases = cases.filter((c) => !c.is_escalated_by_me);
  const openCases = ownCases.filter((c) => c.state === "HUMAN_REVIEW");
  const closedCases = ownCases.filter((c) => c.state === "FINALIZED");
  const blockHoldCases = closedCases.filter((c) => c.final_disposition === "BLOCK_HOLD");
  const escalatedToSenior = cases.filter((c) => c.is_escalated_by_me);

  return {
    totalCases: ownCases.length,
    openCases: openCases.length,
    closedCases: closedCases.length,
    blockHoldCases: blockHoldCases.length,
    escalatedToSenior: escalatedToSenior.length,
  };
}
