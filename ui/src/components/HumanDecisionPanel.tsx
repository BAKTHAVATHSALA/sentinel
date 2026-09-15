import { useState } from "react";
import * as Checkbox from "@radix-ui/react-checkbox";
import { PenGlyph } from "./icons";
import { submitDecision, ApiError } from "../lib/api";
import type { CaseDocument, HumanAction } from "../lib/types";

const ACTION_LABELS: Record<HumanAction, string> = {
  CLEAR: "Clear",
  BLOCK_HOLD: "Block & hold",
  ESCALATE_SENIOR: "Escalate to senior",
};

const REASON_REQUIRED: HumanAction[] = ["BLOCK_HOLD", "ESCALATE_SENIOR"];

/**
 * Human: final operational authority (design spec #8/D). Actions are inert
 * until the analyst explicitly acknowledges the evidence -- authority
 * requires deliberate engagement, not a default-enabled button. Only this
 * panel, through POST /cases/{case_id}/decision, can ever produce
 * BLOCK_HOLD (Safety Invariant 4).
 */
export function HumanDecisionPanel({
  caseDoc,
  onDecided,
}: {
  caseDoc: CaseDocument;
  onDecided: () => void;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [pendingAction, setPendingAction] = useState<HumanAction | null>(null);
  const [reason, setReason] = useState("");
  const [analystId, setAnalystId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reasonRequired = pendingAction ? REASON_REQUIRED.includes(pendingAction) : false;
  const canConfirm = pendingAction !== null && analystId.trim().length > 0 && (!reasonRequired || reason.trim().length > 0);

  async function confirm() {
    if (!pendingAction) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitDecision(caseDoc.case_id, {
        case_id: caseDoc.case_id,
        analyst_id: analystId.trim(),
        action: pendingAction,
        reason: reason.trim() || null,
        evidence_acknowledged: acknowledged,
        client_timestamp: new Date().toISOString(),
      });
      onDecided();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not record the decision. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="p-4">
      <header className="mb-3 flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
        <PenGlyph />
        <span>Human decision</span>
        <span className="text-[var(--color-text-faint)]">&middot; Final authority</span>
      </header>

      <label className="mb-3 flex items-center gap-2 text-[13px] text-[var(--color-text)]">
        <Checkbox.Root
          checked={acknowledged}
          onCheckedChange={(v) => setAcknowledged(v === true)}
          className="flex h-[18px] w-[18px] items-center justify-center border border-[var(--color-rule-strong)] bg-[var(--color-surface)] data-[state=checked]:bg-[var(--color-stable)]"
        >
          <Checkbox.Indicator className="text-[var(--color-ground)]">&#10003;</Checkbox.Indicator>
        </Checkbox.Root>
        I have reviewed the evidence above
      </label>

      {pendingAction === null ? (
        <div className="flex flex-col gap-2">
          {(Object.keys(ACTION_LABELS) as HumanAction[]).map((action) => (
            <button
              key={action}
              type="button"
              disabled={!acknowledged}
              onClick={() => setPendingAction(action)}
              className="border border-[var(--color-rule-strong)] bg-[var(--color-surface)] px-3 py-2 text-left text-[13px] text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-40 enabled:hover:bg-[var(--color-surface-raised)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--color-text)]"
            >
              {ACTION_LABELS[action]}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-2 border border-[var(--color-rule-strong)] p-3">
          <div className="text-[13px] text-[var(--color-text)]">{ACTION_LABELS[pendingAction]}</div>
          <label className="flex flex-col gap-1 text-[12px] text-[var(--color-text-muted)]">
            Analyst ID
            <input
              value={analystId}
              onChange={(e) => setAnalystId(e.target.value)}
              className="border border-[var(--color-rule)] bg-[var(--color-ground)] px-2 py-1 font-mono text-[13px] text-[var(--color-text)]"
              placeholder="analyst_id"
            />
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-[var(--color-text-muted)]">
            Reason {reasonRequired ? "(required)" : "(optional)"}
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              className="resize-none border border-[var(--color-rule)] bg-[var(--color-ground)] px-2 py-1 text-[13px] text-[var(--color-text)]"
            />
          </label>
          {error && <div className="text-[12px] text-[var(--color-critical)]">{error}</div>}
          <div className="mt-1 flex gap-2">
            <button
              type="button"
              onClick={confirm}
              disabled={!canConfirm || submitting}
              className="flex-1 border px-3 py-2 text-[13px] disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                borderColor: pendingAction === "BLOCK_HOLD" ? "var(--color-critical)" : "var(--color-rule-strong)",
                color: pendingAction === "BLOCK_HOLD" ? "var(--color-critical)" : "var(--color-text)",
              }}
            >
              {submitting ? "Recording..." : `Confirm ${ACTION_LABELS[pendingAction].toLowerCase()}`}
            </button>
            <button
              type="button"
              onClick={() => {
                setPendingAction(null);
                setError(null);
              }}
              className="border border-[var(--color-rule)] px-3 py-2 text-[13px] text-[var(--color-text-muted)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
