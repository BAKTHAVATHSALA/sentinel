import { useState } from "react";
import * as Checkbox from "@radix-ui/react-checkbox";
import { PenGlyph } from "./icons";
import { submitDemoDecision } from "../lib/demoApi";
import type { CaseDocument, DecisionResponse, HumanAction } from "../lib/types";

export function DemoHumanDecisionPanel({
  caseDoc,
  onDecided,
}: {
  caseDoc: CaseDocument;
  onDecided: (decision: DecisionResponse) => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [pendingAction, setPendingAction] = useState<HumanAction | null>(null);
  const [reason, setReason] = useState("");
  const defaultSeniorUid = caseDoc.available_seniors?.[0]?.uid ?? "senior_demo_01";
  const [targetSeniorUid, setTargetSeniorUid] = useState(defaultSeniorUid);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEscalation = pendingAction === "ESCALATE_SENIOR";

  const canConfirm =
    pendingAction !== null &&
    acknowledged &&
    reason.trim().length > 0 &&
    (!isEscalation || targetSeniorUid.length > 0);

  async function confirm() {
    if (!pendingAction) return;
    setSubmitting(true);
    setError(null);
    try {
      const decision = await submitDemoDecision(caseDoc.case_id, {
        case_id: caseDoc.case_id,
        analyst_id: "demo_analyst",
        action: pendingAction,
        reason: reason.trim(),
        evidence_acknowledged: true,
        client_timestamp: new Date().toISOString(),
        target_analyst_id: isEscalation ? targetSeniorUid : null,
      });
      onDecided(decision);
    } catch (e: any) {
      setError(e.message ?? "Could not record decision.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 p-5">
      <div className="flex items-center gap-2">
        <PenGlyph />
        <h2 className="text-[14px] font-medium text-[var(--color-text)]">Demo Analyst Decision Authority</h2>
      </div>

      <p className="text-[12px] text-[var(--color-text-muted)]">
        Deterministic policy holds the authorization. Human fraud authority can clear, block, or escalate this transaction to a senior analyst.
      </p>

      {/* Mandatory Evidence Acknowledgment */}
      <label className="flex items-start gap-2 text-[12px] text-[var(--color-text)] cursor-pointer">
        <Checkbox.Root
          checked={acknowledged}
          onCheckedChange={(checked) => setAcknowledged(Boolean(checked))}
          className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center border border-[var(--color-rule-strong)] bg-[var(--color-surface)] data-[state=checked]:bg-[var(--color-surface-raised)]"
        >
          <Checkbox.Indicator className="text-[11px] text-[var(--color-text)]">&#10003;</Checkbox.Indicator>
        </Checkbox.Root>
        <span>I have inspected the gathered exhibits, Gemini grounded findings, and policy ledger before taking action.</span>
      </label>

      {/* Decision Buttons */}
      <div className="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          disabled={!acknowledged}
          onClick={() => {
            setPendingAction("CLEAR");
            setError(null);
          }}
          className={`border px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-40 ${
            pendingAction === "CLEAR"
              ? "border-[var(--color-stable)] bg-[var(--color-stable-soft)] text-[var(--color-stable)]"
              : "border-[var(--color-rule)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
        >
          Clear Transaction
        </button>

        <button
          type="button"
          disabled={!acknowledged}
          onClick={() => {
            setPendingAction("BLOCK_HOLD");
            setError(null);
          }}
          className={`border px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-40 ${
            pendingAction === "BLOCK_HOLD"
              ? "border-[var(--color-critical)] bg-[var(--color-critical-soft)] text-[var(--color-critical)]"
              : "border-[var(--color-rule)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
        >
          Block & Hold
        </button>

        <button
          type="button"
          disabled={!acknowledged}
          onClick={() => {
            setPendingAction("ESCALATE_SENIOR");
            setError(null);
          }}
          className={`border px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-40 ${
            pendingAction === "ESCALATE_SENIOR"
              ? "border-[var(--color-caution)] bg-[var(--color-caution-soft)] text-[var(--color-caution)]"
              : "border-[var(--color-rule)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
        >
          Escalate to Senior Analyst
        </button>
      </div>

      {pendingAction && (
        <div className="flex flex-col gap-2 rounded border border-[var(--color-rule)] bg-[var(--color-surface)] p-3">
          {isEscalation && (
            <label className="flex flex-col gap-1 text-[12px] text-[var(--color-text-muted)]">
              Assign to Senior Analyst:
              <select
                value={targetSeniorUid}
                onChange={(e) => setTargetSeniorUid(e.target.value)}
                className="border border-[var(--color-rule)] bg-[var(--color-surface-raised)] px-2 py-1 text-[12px] text-[var(--color-text)] focus:outline-none"
              >
                {(caseDoc.available_seniors && caseDoc.available_seniors.length > 0
                  ? caseDoc.available_seniors
                  : [
                      { uid: "senior_demo_01", display_name: "Elena Cho (Senior Fraud Analyst)" },
                      { uid: "senior_demo_02", display_name: "Marcus Vance (Lead Risk Officer)" },
                    ]
                ).map((senior) => (
                  <option key={senior.uid} value={senior.uid}>
                    {senior.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="text-[12px] text-[var(--color-text-muted)]">
            Analyst Reason / Justification <span className="text-[var(--color-caution)]">*</span>:
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={
              isEscalation
                ? "Document justification for escalating to senior analyst review..."
                : `Document justification for choosing ${pendingAction === "CLEAR" ? "Clear" : "Block & Hold"}...`
            }
            rows={2}
            maxLength={500}
            className="w-full resize-none border border-[var(--color-rule)] bg-[var(--color-surface-raised)] p-2 text-[12px] text-[var(--color-text)] placeholder:text-[var(--color-text-faint)] focus:outline-none"
          />

          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-[var(--color-text-faint)]">
              {500 - reason.length} characters remaining
            </span>
            <button
              type="button"
              disabled={!canConfirm || submitting}
              onClick={confirm}
              className="border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-4 py-1.5 text-[12px] font-medium text-[var(--color-text)] hover:border-[var(--color-text-muted)] disabled:opacity-40"
            >
              {submitting
                ? "Recording..."
                : isEscalation
                  ? "Confirm Escalation"
                  : `Confirm ${pendingAction === "CLEAR" ? "Clear" : "Block & Hold"}`}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="border border-[var(--color-critical)] bg-[var(--color-critical-soft)] p-2 text-[12px] text-[var(--color-critical)]">
          {error}
        </div>
      )}
    </div>
  );
}
