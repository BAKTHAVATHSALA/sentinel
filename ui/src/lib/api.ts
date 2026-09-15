import type { CaseDocument, DecisionResponse, HumanDecisionRequest, QueueCaseSummary } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? `Request to ${path} failed`);
  }
  return response.json() as Promise<T>;
}

/** GET /cases -- the queue view (Build Checklist Phase 5.1/5.2). */
export function fetchQueue(): Promise<QueueCaseSummary[]> {
  return request<QueueCaseSummary[]>("/cases");
}

/** GET /cases/{case_id} -- full case detail (Build Checklist Phase 5.1/5.3). */
export function fetchCase(caseId: string): Promise<CaseDocument> {
  return request<CaseDocument>(`/cases/${encodeURIComponent(caseId)}`);
}

/** POST /cases/{case_id}/decision -- record a human analyst decision. */
export function submitDecision(caseId: string, body: HumanDecisionRequest): Promise<DecisionResponse> {
  return request<DecisionResponse>(`/cases/${encodeURIComponent(caseId)}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
