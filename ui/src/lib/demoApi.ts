import { ApiError } from "./api";
import { setAnalystIdentity } from "./analystIdentity";
import type {
  CaseDocument,
  DecisionResponse,
  HumanDecisionRequest,
  QueueCaseSummary,
  Transaction,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const SESSION_TOKEN_KEY = "sentinel_demo_session_token";
const SESSION_ID_KEY = "sentinel_demo_session_id";

export interface DemoSessionInfo {
  session_token: string;
  session_id: string;
  expires_at: number;
  display_name: string;
  role: string;
}

/**
 * Ensure an active, cryptographically signed capability token exists in sessionStorage.
 * If none exists or current token is expired, calls POST /demo/session to bootstrap one.
 */
export async function ensureDemoSession(): Promise<string> {
  const existingToken = sessionStorage.getItem(SESSION_TOKEN_KEY);
  if (existingToken) {
    // Quick validation probe
    try {
      const probe = await fetch(`${API_BASE}/demo/session`, {
        headers: { "X-Sentinel-Demo-Session": existingToken },
      });
      if (probe.ok) {
        setAnalystIdentity({ displayName: "Demo Analyst", role: "ANALYST" });
        return existingToken;
      }
    } catch {
      // Fall through to bootstrap
    }
  }

  // Bootstrap new session
  const res = await fetch(`${API_BASE}/demo/session`, { method: "POST" });
  if (!res.ok) {
    throw new ApiError(res.status, "Failed to initialize demo session. Please try again.");
  }
  const data = (await res.json()) as DemoSessionInfo;
  sessionStorage.setItem(SESSION_TOKEN_KEY, data.session_token);
  sessionStorage.setItem(SESSION_ID_KEY, data.session_id);
  setAnalystIdentity({ displayName: "Demo Analyst", role: "ANALYST" });
  return data.session_token;
}

export function getActiveDemoSessionId(): string | null {
  return sessionStorage.getItem(SESSION_ID_KEY);
}

async function demoRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await ensureDemoSession();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Sentinel-Demo-Session": token,
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(
      response.status,
      body.detail ?? body.message ?? `Demo request to ${path} failed`,
    );
  }

  return response.json() as Promise<T>;
}

/** GET /demo/cases -- list open demo cases for the active session */
export function fetchDemoQueue(): Promise<QueueCaseSummary[]> {
  return demoRequest<QueueCaseSummary[]>("/demo/cases");
}

/** GET /demo/cases?scope=dashboard -- list all demo cases for metrics */
export function fetchDemoDashboardCases(): Promise<QueueCaseSummary[]> {
  return demoRequest<QueueCaseSummary[]>("/demo/cases?scope=dashboard");
}

/** GET /demo/cases/{case_id} -- case detail + optional live counterfactual */
export function fetchDemoCase(caseId: string, simulateWithoutFactId?: string): Promise<CaseDocument> {
  const query = simulateWithoutFactId ? `?simulate_without=${encodeURIComponent(simulateWithoutFactId)}` : "";
  return demoRequest<CaseDocument>(`/demo/cases/${encodeURIComponent(caseId)}${query}`);
}

/** POST /demo/cases/{case_id}/decision -- record human decision */
export function submitDemoDecision(caseId: string, body: HumanDecisionRequest): Promise<DecisionResponse> {
  return demoRequest<DecisionResponse>(`/demo/cases/${encodeURIComponent(caseId)}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** POST /demo/reset -- restore 10 cases to pristine initial state */
export function resetDemoSession(): Promise<{ status: string; message: string }> {
  return demoRequest<{ status: string; message: string }>("/demo/reset", {
    method: "POST",
  });
}

/** GET /demo/sample-transactions -- sample clean and high-risk payloads */
export function fetchDemoSampleTransactions(): Promise<{ clean: Transaction; high_risk: Transaction }> {
  return fetch(`${API_BASE}/demo/sample-transactions`).then((r) => r.json());
}
