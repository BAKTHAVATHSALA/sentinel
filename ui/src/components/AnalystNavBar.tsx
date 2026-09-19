import { Link } from "react-router-dom";
import { useAnalystIdentity } from "../lib/analystIdentity";
import { useAuth } from "../lib/auth";

const ROLE_LABELS: Record<string, string> = {
  ANALYST: "Analyst",
  SENIOR_ANALYST: "Senior Analyst",
};

/**
 * Persistent navigation present on every authenticated analyst screen
 * (Case Queue, Case Detail, decision confirmation, unauthorized notice):
 * Sentinel wordmark, My Cases, the caller's own display name/role (from
 * the X-Analyst-Display-Name/X-Analyst-Role response headers -- see
 * lib/api.ts), and Logout. Role is never computed or guessed here; it is
 * exactly what the server already resolved for the most recent request.
 */
export function AnalystNavBar() {
  const identity = useAnalystIdentity();
  const { signOut } = useAuth();

  return (
    <nav className="flex items-center justify-between border-b border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-2">
      <div className="flex items-center gap-4">
        <span className="text-[13px] tracking-wide text-[var(--color-text-faint)]">SENTINEL</span>
        <Link to="/" className="text-[13px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          My Cases
        </Link>
      </div>
      <div className="flex items-center gap-3 text-[12px] text-[var(--color-text-muted)]">
        {identity && (
          <>
            <span className="text-[var(--color-text)]">{identity.displayName}</span>
            <span>{ROLE_LABELS[identity.role] ?? identity.role}</span>
          </>
        )}
        <button
          type="button"
          onClick={() => signOut()}
          className="border border-[var(--color-rule)] px-2 py-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          Logout
        </button>
      </div>
    </nav>
  );
}
