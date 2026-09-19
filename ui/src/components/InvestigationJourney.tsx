import type { TransactionInvestigationResult } from "../lib/types";

/**
 * The premium replacement for the old static pipeline dots (build.md
 * Section 13). Node states are derived ONLY from real, known facts:
 * - "waiting": nothing submitted yet.
 * - "active": a real POST /transactions request is in flight. Every stage
 *   after Transaction pulses simultaneously -- there is no per-stage
 *   timing signal from the backend (Section 14), so this deliberately
 *   never implies "Detection finished at second 1, Evidence at second 2".
 * - "complete" / "skipped" / "error": derived from the real response only,
 *   once it lands. A clean transaction that skipped investigation shows
 *   Evidence/Reasoning/Robustness/Policy as "skipped", never "complete".
 */

export type JourneyPhase = "idle" | "running" | "done" | "request-failed";

export type JourneyNodeState = "waiting" | "active" | "complete" | "skipped" | "error";

export interface JourneyNode {
  label: string;
  state: JourneyNodeState;
}

const STAGE_LABELS = ["Transaction", "Detection", "Evidence Agent", "AI Reasoning", "Robustness", "Policy", "Routing"];

export function deriveJourneyNodes(phase: JourneyPhase, result: TransactionInvestigationResult | null): JourneyNode[] {
  if (phase === "idle") return STAGE_LABELS.map((label) => ({ label, state: "waiting" }));

  if (phase === "running") {
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

export function InvestigationJourney({ phase, result }: { phase: JourneyPhase; result: TransactionInvestigationResult | null }) {
  const nodes = deriveJourneyNodes(phase, result);
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
