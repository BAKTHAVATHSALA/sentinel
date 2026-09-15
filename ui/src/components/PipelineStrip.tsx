import type { CaseDocument } from "../lib/types";

/**
 * The investigation story made literal: Detection -> Evidence -> Reasoning
 * -> Robustness -> Policy -> Human Decision (design spec revision #5).
 * Advisory stages (Reasoning, Robustness) render soft-outline; decision
 * stages (Policy, Human) render solid-fill -- the same authority split
 * carried through the verdict rail (revision #8), stated a second way.
 */

type StageStatus = "done" | "advisory" | "decision" | "pending" | "skipped" | "failed";

interface Stage {
  label: string;
  status: StageStatus;
  detail: string;
  kind: "system" | "advisory" | "decision";
}

function deriveStages(caseDoc: CaseDocument): Stage[] {
  const { detection, evidence_bundle, findings, robustness, policy_decision, state } = caseDoc;

  const investigated = evidence_bundle !== null;

  const evidenceStage: Stage = investigated
    ? {
        label: "Evidence",
        status: evidence_bundle!.completeness === "COMPLETE" ? "done" : "failed",
        detail: evidence_bundle!.completeness === "COMPLETE" ? "Complete" : "Partial",
        kind: "system",
      }
    : { label: "Evidence", status: "skipped", detail: "Not required", kind: "system" };

  const reasoningStage: Stage = !investigated
    ? { label: "Reasoning", status: "skipped", detail: "Not required", kind: "advisory" }
    : findings !== null
      ? { label: "Reasoning", status: "advisory", detail: "Success", kind: "advisory" }
      : { label: "Reasoning", status: "failed", detail: "Failed", kind: "advisory" };

  const robustnessStage: Stage = robustness
    ? {
        label: "Robustness",
        status: "advisory",
        detail: robustness.classification === "FRAGILE" ? "Fragile" : "Robust",
        kind: "advisory",
      }
    : { label: "Robustness", status: "skipped", detail: investigated ? "Not scored" : "Not required", kind: "advisory" };

  const policyStage: Stage = policy_decision
    ? {
        label: "Policy",
        status: "decision",
        detail: policy_decision.outcome === "AUTO_RESOLVE" ? "Auto-resolve" : "Escalate",
        kind: "decision",
      }
    : { label: "Policy", status: "skipped", detail: "Not required", kind: "decision" };

  const humanDetail =
    state === "AUTO_RESOLVED"
      ? "No action needed"
      : state === "FINALIZED"
        ? caseDoc.final_disposition ?? "Recorded"
        : state === "HUMAN_REVIEW"
          ? "Awaiting"
          : "Pending";
  const humanStatus: StageStatus = state === "FINALIZED" ? "decision" : state === "HUMAN_REVIEW" ? "pending" : "skipped";

  return [
    {
      label: "Detection",
      status: "done",
      detail: `${detection.risk_band === "LOW" ? "Low" : detection.risk_band === "MEDIUM" ? "Medium" : "High"} risk`,
      kind: "system",
    },
    evidenceStage,
    reasoningStage,
    robustnessStage,
    policyStage,
    { label: "Human decision", status: humanStatus, detail: humanDetail, kind: "decision" },
  ];
}

const STATUS_COLOR: Record<StageStatus, string> = {
  done: "text-[var(--color-stable)]",
  advisory: "text-[var(--color-text)]",
  decision: "text-[var(--color-text)]",
  pending: "text-[var(--color-caution)]",
  skipped: "text-[var(--color-text-faint)]",
  failed: "text-[var(--color-critical)]",
};

export function PipelineStrip({ caseDoc }: { caseDoc: CaseDocument }) {
  const stages = deriveStages(caseDoc);
  return (
    <div className="flex items-stretch gap-0 border border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-3">
      {stages.map((stage, i) => (
        <div key={stage.label} className="flex flex-1 items-center">
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-1.5">
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  stage.kind === "decision" && stage.status !== "skipped" ? "bg-current" : "border border-current bg-transparent"
                } ${STATUS_COLOR[stage.status]}`}
              />
              <span className="text-[13px] text-[var(--color-text)]">{stage.label}</span>
            </div>
            <span className={`pl-3.5 text-[12px] ${STATUS_COLOR[stage.status]}`}>{stage.detail}</span>
          </div>
          {i < stages.length - 1 && <div className="mx-3 mt-[-14px] h-px flex-1 self-center bg-[var(--color-rule)]" />}
        </div>
      ))}
    </div>
  );
}
