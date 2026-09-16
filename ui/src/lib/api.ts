import { firebaseAuth } from "./firebase";
import type { CaseDocument, DecisionResponse, HumanDecisionRequest, QueueCaseSummary } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Your session has expired. Please sign in again.",
  403: "You do not have access to this case.",
  409: "This case was already decided or reassigned by someone else.",
};

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
    throw new ApiError(response.status, STATUS_MESSAGES[response.status] ?? body.detail ?? `Request to ${path} failed`);
  }
  return response.json() as Promise<T>;
}

/** GET /cases -- the queue view, scoped to the authenticated caller (Build
 * Checklist Phase 5.1/5.2, V1 Authoritative Ruling Part 6). */
export function fetchQueue(): Promise<QueueCaseSummary[]> {
  return request<QueueCaseSummary[]>("/cases");
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
