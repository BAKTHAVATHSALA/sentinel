import { firebaseAuth } from "./firebase";
import { setAnalystIdentity, type AnalystIdentity } from "./analystIdentity";
import type {
  CaseDocument,
  DecisionResponse,
  HumanDecisionRequest,
  QueueCaseSummary,
  Transaction,
  TransactionInvestigationResult,
  TransactionLiveStatus,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function formatErrorDetail(detail: unknown): string {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (typeof item === "object" && item !== null) {
          const loc = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
          const msg = item.msg || item.message || JSON.stringify(item);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      })
      .join("; ");
  }
  if (typeof detail === "object" && detail !== null) {
    const obj = detail as Record<string, any>;
    return obj.message || obj.msg || JSON.stringify(detail);
  }
  return String(detail);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: unknown) {
    super(formatErrorDetail(message) || "Request failed");
    this.status = status;
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Your session has expired. Please sign in again.",
  403: "You do not have access to this case.",
  404: "This case is not available.",
  409: "This case was already decided or reassigned by someone else.",
};

/** GET /cases and GET /cases/{case_id} additively return the caller's own
 * server-resolved identity as response headers (never a new endpoint, never
 * client-supplied) -- capture it here so the persistent nav bar can render
 * it without every page having to know or care which call happened to
 * carry it. */
function captureAnalystIdentity(headers: Headers): void {
  const displayName = headers.get("X-Analyst-Display-Name");
  const role = headers.get("X-Analyst-Role");
  if (displayName && (role === "ANALYST" || role === "SENIOR_ANALYST")) {
    setAnalystIdentity({ displayName, role } satisfies AnalystIdentity);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const idToken = await firebaseAuth.currentUser?.getIdToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(
      response.status,
      STATUS_MESSAGES[response.status] ?? body.detail ?? body.message ?? `Request to ${path} failed`,
    );
  }
  captureAnalystIdentity(response.headers);
  return response.json() as Promise<T>;
}

/** GET /cases -- the queue view, scoped to the authenticated caller (Build
 * Checklist Phase 5.1/5.2, V1 Authoritative Ruling Part 6). */
export function fetchQueue(): Promise<QueueCaseSummary[]> {
  return request<QueueCaseSummary[]>("/cases");
}

/** GET /cases?scope=dashboard -- the same endpoint, additively broadened for
 * the dashboard metric cards: this analyst's own open + closed cases, plus
 * cases they escalated (`is_escalated_by_me`), still scoped entirely to the
 * authenticated caller. The queue page uses this as its single data source
 * and derives both the visible queue table and the metric counts from it,
 * rather than issuing a second fetch (`fetchQueue` above remains for any
 * caller that only wants the plain open-queue view). */
export function fetchDashboardCases(): Promise<QueueCaseSummary[]> {
  return request<QueueCaseSummary[]>("/cases?scope=dashboard");
}

/** GET /cases/{case_id} -- full case detail (Build Checklist Phase 5.1/5.3).
 * `simulateWithoutFactId` additively requests a fresh, non-persisted
 * counterfactual re-evaluation (mega-prompt Section 9/10). */
export function fetchCase(caseId: string, simulateWithoutFactId?: string): Promise<CaseDocument> {
  const query = simulateWithoutFactId ? `?simulate_without=${encodeURIComponent(simulateWithoutFactId)}` : "";
  return request<CaseDocument>(`/cases/${encodeURIComponent(caseId)}${query}`);
}

/** POST /cases/{case_id}/decision -- record a human analyst decision. */
export function submitDecision(caseId: string, body: HumanDecisionRequest): Promise<DecisionResponse> {
  return request<DecisionResponse>(`/cases/${encodeURIComponent(caseId)}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** POST /transactions -- the Transaction Console's only backend call
 * (Detection through Policy, then Firestore write and, when escalated, real
 * round-robin assignment). Deliberately unauthenticated server-side
 * (services/api/main.py) and independent of the signed-in analyst session:
 * the console never follows this with GET /cases/{case_id} and never checks
 * whether the current session owns the resulting case -- that is the
 * separate, authenticated Analyst Portal's job. */
export function postTransaction(body: Transaction): Promise<TransactionInvestigationResult> {
  return request<TransactionInvestigationResult>("/transactions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** GET /transactions/{transaction_id}/status -- the Transaction Console's
 * poll target while the POST /transactions call above is still in flight, so
 * the pipeline visualization can reflect genuine backend milestones
 * (real Firestore writes made mid-request by run_pipeline) instead of a
 * single simultaneous pulse. Unauthenticated, additive, and strictly less
 * detailed than postTransaction's own final response -- see
 * services/api/main.py:TransactionStatusResponse. */
export function fetchTransactionStatus(transactionId: string): Promise<TransactionLiveStatus> {
  return request<TransactionLiveStatus>(`/transactions/${encodeURIComponent(transactionId)}/status`);
}
