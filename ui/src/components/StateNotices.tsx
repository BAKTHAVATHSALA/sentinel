import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";

/** Realistic states (design spec #15/#10): partial evidence, reasoning
 * failed, and clean/no-investigation transactions are stated plainly, in
 * the interface's voice -- never hidden, never a blank panel. */

export function PartialEvidenceBanner({ missing }: { missing: string[] }) {
  return (
    <div className="border border-[var(--color-caution)] bg-[var(--color-caution-soft)] p-3 text-[13px] text-[var(--color-caution)]">
      Evidence is incomplete. The investigation could not confirm:{" "}
      <span className="font-mono">{missing.join(", ")}</span>.
    </div>
  );
}

export function ReasoningFailedNotice() {
  return (
    <div className="border border-[var(--color-critical)] bg-[var(--color-critical-soft)] p-4 text-[13px] text-[var(--color-critical)]">
      Gemini reasoning did not complete for this case after a schema-only reprompt. Policy escalated automatically
      (the fail-safe default rule) -- this is the system working as designed, not a broken page.
    </div>
  );
}

/**
 * A case can have no evidence_bundle (never investigated) for two different
 * reasons since the orchestrator's clean-transaction risk-band fix: a
 * CLEAN + LOW transaction that auto-resolved (AUTO_RESOLVED), or a CLEAN but
 * MEDIUM/HIGH-risk transaction that still needs a human decision even though
 * there was nothing to investigate (HUMAN_REVIEW). Copy must not claim
 * "resolved automatically" for the second case -- that would be false on a
 * case actually sitting in the analyst's own queue awaiting their decision.
 */
export function EmptyInvestigationNotice({ state }: { state: string }) {
  return (
    <div className="p-4 text-[13px] text-[var(--color-text-muted)]">
      {state === "AUTO_RESOLVED"
        ? "No anomaly tags were detected. This transaction did not require investigation and resolved automatically."
        : "No anomaly tags were detected, but the risk assessment was not LOW, so this case still requires a human decision. There is no automated evidence to review -- Detection alone determined this outcome."}
    </div>
  );
}

export function CaseDetailError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-start gap-2 p-6 text-[13px] text-[var(--color-critical)]">
      <span>{message}</span>
      <button
        type="button"
        onClick={onRetry}
        className="border border-[var(--color-critical)] px-3 py-1.5 text-[var(--color-critical)]"
      >
        Retry
      </button>
    </div>
  );
}

/** A generic, non-leaking terminal state for a case the caller cannot view
 * -- whether because it doesn't exist or because it isn't assigned to them
 * (the backend already makes both indistinguishable, see
 * services/api/cases.py:get_case). No "Retry" affordance -- retrying a 404
 * won't change the outcome -- only a way back to real work and a way out. */
export function CaseUnavailableNotice({ message }: { message: string }) {
  const { signOut } = useAuth();
  return (
    <div className="flex flex-col items-start gap-3 p-6 text-[13px] text-[var(--color-text-muted)]">
      <p>{message}</p>
      <div className="flex gap-2">
        <Link to="/" className="border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-3 py-1.5 text-[13px] text-[var(--color-text)]">
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
    </div>
  );
}

export function LoadingSkeleton() {
  return (
    <div className="flex h-full animate-none gap-0" aria-busy="true" aria-label="Loading case">
      <div className="w-[280px] border-r border-[var(--color-rule)] p-4">
        <div className="h-4 w-24 bg-[var(--color-surface-raised)]" />
        <div className="mt-4 h-8 w-32 bg-[var(--color-surface-raised)]" />
        <div className="mt-6 h-16 w-full bg-[var(--color-surface-raised)]" />
      </div>
      <div className="flex-1 p-4">
        <div className="h-6 w-48 bg-[var(--color-surface-raised)]" />
        <div className="mt-4 h-24 w-full bg-[var(--color-surface-raised)]" />
        <div className="mt-3 h-24 w-full bg-[var(--color-surface-raised)]" />
      </div>
      <div className="w-[340px] border-l border-[var(--color-rule)] p-4">
        <div className="h-20 w-full bg-[var(--color-surface-raised)]" />
        <div className="mt-4 h-20 w-full bg-[var(--color-surface-raised)]" />
      </div>
    </div>
  );
}
