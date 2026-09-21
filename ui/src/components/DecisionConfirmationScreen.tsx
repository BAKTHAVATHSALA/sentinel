import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import type { DecisionResponse } from "../lib/types";

/**
 * Rendered immediately after a human decision succeeds -- built entirely
 * from the real DecisionResponse the backend just returned (case_id, state,
 * final_disposition, decided_at, target_analyst_display_name). This screen
 * NEVER triggers GET /cases/{case_id}: for ESCALATE_SENIOR specifically,
 * ownership has just moved away from the caller, so a refetch would
 * immediately (and correctly) fail the ownership check -- showing this
 * confirmation from the decision response itself avoids that collision
 * entirely, for all three actions, not just escalation.
 */
export function DecisionConfirmationScreen({ decision }: { decision: DecisionResponse }) {
  const { user } = useAuth();
  const isEscalation = decision.final_disposition === null;

  if (isEscalation) {
    return (
      <div className="mx-auto max-w-[560px] p-6">
        <div className="border border-[var(--color-caution)] bg-[var(--color-caution-soft)] p-5">
          <p className="text-[16px] text-[var(--color-caution)]">Case Escalated Successfully</p>
          <p className="mt-3 text-[12px] text-[var(--color-text-muted)]">
            Case: <span className="font-mono text-[var(--color-text)]">{decision.case_id}</span>
          </p>
          <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
            Status: <span className="text-[var(--color-text)]">{decision.state}</span>
          </p>
          {decision.target_analyst_display_name && (
            <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
              Escalated to: <span className="text-[var(--color-text)]">{decision.target_analyst_display_name}</span>
            </p>
          )}
          <p className="mt-3 text-[13px] text-[var(--color-text-muted)]">
            Ownership of this case has moved to the selected senior analyst. You no longer have access to it.
          </p>
        </div>
        <NextSteps />
      </div>
    );
  }

  const isBlockHold = decision.final_disposition === "BLOCK_HOLD";
  const title = isBlockHold ? "Transaction Blocked / Held" : "Case Cleared";
  // BLOCK_HOLD is the one genuinely severe human action (Safety Invariant 4)
  // -- red here, consistent with every other place it's shown (the decision
  // button itself, the dashboard metric card, the case header). CLEAR is a
  // successful, informational outcome, same teal as elsewhere.
  const accentColor = isBlockHold ? "var(--color-critical)" : "var(--color-stable)";
  const accentSoft = isBlockHold ? "var(--color-critical-soft)" : "var(--color-stable-soft)";
  return (
    <div className="mx-auto max-w-[560px] p-6">
      <div className="border p-5" style={{ borderColor: accentColor, backgroundColor: accentSoft }}>
        <p className="text-[16px]" style={{ color: accentColor }}>
          {title}
        </p>
        <p className="mt-3 text-[12px] text-[var(--color-text-muted)]">
          Case: <span className="font-mono text-[var(--color-text)]">{decision.case_id}</span>
        </p>
        <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
          Decision: <span className="text-[var(--color-text)]">{decision.final_disposition}</span>
        </p>
        <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
          Actor: <span className="text-[var(--color-text)]">{user?.email}</span>
        </p>
        <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
          Decided at: <span className="text-[var(--color-text)]">{decision.decided_at}</span>
        </p>
        <p className="mt-3 text-[13px] text-[var(--color-text-muted)]">
          This decision is finalized ({decision.state}). No further action is available on this case.
        </p>
      </div>
      <NextSteps />
    </div>
  );
}

function NextSteps() {
  const { signOut } = useAuth();
  return (
    <div className="mt-4 flex gap-2">
      <Link
        to="/"
        className="border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-3 py-1.5 text-[13px] text-[var(--color-text)]"
      >
        Back to My Cases
      </Link>
      <button
        type="button"
        onClick={() => signOut()}
        className="border border-[var(--color-rule)] px-3 py-1.5 text-[13px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
      >
        Logout
      </button>
    </div>
  );
}
