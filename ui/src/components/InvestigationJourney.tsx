import type { CaseState, TransactionInvestigationResult, TransactionLiveStatus } from "../lib/types";

/**
 * The premium replacement for the old static pipeline dots (build.md
 * Section 13). Node states are derived ONLY from real, known facts:
 * - "waiting": nothing submitted yet, or a stage genuinely hasn't started.
 * - "active": the real POST /transactions request is in flight AND the
 *   polled GET /transactions/{id}/status (services/api/main.py) reports
 *   this is the stage currently running -- see deriveRunningNodes below.
 *   When no live status has landed yet (liveStatus omitted/null), every
 *   stage after Transaction pulses together as a safe fallback, same as
 *   before -- never a fabricated per-stage timeline in that case either.
 * - "complete" / "skipped" / "error": derived from the real response (done)
 *   or the real polled status (running) only. A clean transaction that
 *   skipped investigation shows Evidence/Reasoning/Robustness/Policy as
 *   "skipped", never "complete".
 */

export type JourneyPhase = "idle" | "running" | "done" | "request-failed";

export type JourneyNodeState = "waiting" | "active" | "complete" | "skipped" | "error";

export interface JourneyNode {
  label: string;
  state: JourneyNodeState;
}

const STAGE_LABELS = ["Transaction", "Detection", "Evidence Agent", "AI Reasoning", "Robustness", "Policy", "Routing"];

// CaseState values where investigation (if any was going to happen) has
// concluded and the case is routing to its disposition -- Policy already
// ran (AUTO_RESOLVE/ESCALATE) or deliberately never ran (the clean-but-not-
// LOW-risk escalation path, shared/pipeline/orchestrator.py:
// _escalate_clean_transaction_with_elevated_risk). ESCALATED is the
// transient moment between Policy deciding ESCALATE and the case actually
// landing in HUMAN_REVIEW.
const ROUTING_STATES = new Set<CaseState>(["ESCALATED", "AUTO_RESOLVED", "HUMAN_REVIEW", "FINALIZED"]);
const RESOLVED_STATES = new Set<CaseState>(["AUTO_RESOLVED", "HUMAN_REVIEW", "FINALIZED"]);

function stageNodes(states: JourneyNodeState[]): JourneyNode[] {
  return STAGE_LABELS.map((label, i) => ({ label, state: states[i] }));
}

/** Derives real per-stage progress from a polled TransactionLiveStatus while
 * POST /transactions is still in flight. Every branch reads only fields the
 * backend actually wrote (CaseState transitions + the has_* flags from real
 * Firestore documents) -- there is no timer and no assumption about how
 * long any stage takes. */
function deriveRunningNodes(live: TransactionLiveStatus): JourneyNode[] {
  if (!live.case_id || !live.state) {
    // The pipeline's first Firestore write (post-Detection) hasn't landed yet.
    return stageNodes(["complete", "active", "waiting", "waiting", "waiting", "waiting", "waiting"]);
  }

  if (ROUTING_STATES.has(live.state)) {
    // investigated === has_policy_decision is the running-phase analog of
    // the "done" branch's `result.outcome !== null` skip signal below --
    // Policy evaluating is exactly what distinguishes a real investigation
    // from a clean transaction that skipped straight to routing.
    const investigated = live.has_policy_decision;
    const midState: JourneyNodeState = investigated ? "complete" : "skipped";
    const routingState: JourneyNodeState = RESOLVED_STATES.has(live.state) ? "complete" : "active";
    return stageNodes(["complete", "complete", midState, midState, midState, midState, routingState]);
  }

  if (live.state === "REASONING_FAILED") {
    // Reasoning truly failed, but Sentinel's Policy still evaluates and
    // still reaches a disposition (fail-safe behavior, not a pipeline
    // halt) -- Robustness alone is skipped, since the orchestrator only
    // computes it when Reasoning succeeds.
    return stageNodes(["complete", "complete", "complete", "error", "skipped", "active", "waiting"]);
  }

  if (live.state === "DETECTED" || live.state === "FLAGGED" || live.state === "INVESTIGATING") {
    return stageNodes(["complete", "complete", "active", "waiting", "waiting", "waiting", "waiting"]);
  }

  if (live.state === "EVIDENCE_READY" || live.state === "EVIDENCE_PARTIAL") {
    return stageNodes(["complete", "complete", "complete", "active", "waiting", "waiting", "waiting"]);
  }

  // REASONED and not yet routing.
  if (!live.has_robustness) {
    return stageNodes(["complete", "complete", "complete", "complete", "active", "waiting", "waiting"]);
  }

  const policyState: JourneyNodeState = live.has_policy_decision ? "complete" : "active";
  const routingState: JourneyNodeState = live.has_policy_decision ? "active" : "waiting";
  return stageNodes(["complete", "complete", "complete", "complete", "complete", policyState, routingState]);
}

export function deriveJourneyNodes(
  phase: JourneyPhase,
  result: TransactionInvestigationResult | null,
  liveStatus?: TransactionLiveStatus | null,
): JourneyNode[] {
  if (phase === "idle") return STAGE_LABELS.map((label) => ({ label, state: "waiting" }));

  if (phase === "running") {
    if (liveStatus) return deriveRunningNodes(liveStatus);
    return STAGE_LABELS.map((label, i) => ({ label, state: i === 0 ? "complete" : "active" }));
  }

  if (phase === "request-failed") {
    return STAGE_LABELS.map((label, i) => ({ label, state: i === 0 ? "complete" : "error" }));
  }

  if (!result) return STAGE_LABELS.map((label) => ({ label, state: "waiting" }));

  const investigated = result.outcome !== null;
  return [
    { label: "Transaction", state: "complete" },
    { label: "Detection", state: "complete" },
    { label: "Evidence Agent", state: investigated ? "complete" : "skipped" },
    { label: "AI Reasoning", state: investigated ? "complete" : "skipped" },
    { label: "Robustness", state: investigated ? "complete" : "skipped" },
    { label: "Policy", state: investigated ? "complete" : "skipped" },
    { label: "Routing", state: "complete" },
  ];
}

const STATE_STYLE: Record<JourneyNodeState, string> = {
  waiting: "border-[var(--color-rule)] text-[var(--color-text-faint)]",
  active: "border-[var(--color-stable)] text-[var(--color-stable)] journey-node-active",
  complete: "border-[var(--color-stable)] bg-[var(--color-stable)] text-[var(--color-ground)]",
  skipped: "border-[var(--color-rule)] text-[var(--color-text-faint)]",
  error: "border-[var(--color-critical)] text-[var(--color-critical)]",
};

function NodeGlyph({ state }: { state: JourneyNodeState }) {
  if (state === "complete") return <span aria-hidden="true">&#10003;</span>;
  if (state === "error") return <span aria-hidden="true">&#10005;</span>;
  if (state === "skipped") return <span aria-hidden="true">&ndash;</span>;
  return null;
}

export function InvestigationJourney({
  phase,
  result,
  liveStatus,
}: {
  phase: JourneyPhase;
  result: TransactionInvestigationResult | null;
  liveStatus?: TransactionLiveStatus | null;
}) {
  const nodes = deriveJourneyNodes(phase, result, liveStatus);
  return (
    <div className="flex items-start" role="list" aria-label="Investigation journey">
      {nodes.map((node, i) => (
        <div key={node.label} className="flex flex-1 items-start last:flex-none" role="listitem">
          <div className="flex flex-col items-center gap-1.5">
            <div
              className={`flex h-7 w-7 items-center justify-center rounded-full border text-[13px] ${STATE_STYLE[node.state]}`}
            >
              <NodeGlyph state={node.state} />
            </div>
            <span
              className={`w-[84px] text-center text-[11px] leading-tight ${
                node.state === "waiting" || node.state === "skipped" ? "text-[var(--color-text-faint)]" : "text-[var(--color-text-muted)]"
              }`}
            >
              {node.label}
            </span>
          </div>
          {i < nodes.length - 1 && (
            <div className="mt-3.5 h-px flex-1 bg-[var(--color-rule)]">
              <div
                className={`journey-connector-fill h-px bg-[var(--color-stable)] ${
                  node.state === "complete" ? "w-full" : "w-0"
                }`}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
