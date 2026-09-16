import { useEffect, useState } from "react";
import { fetchQueue, ApiError } from "../lib/api";
import { QueueTable } from "../components/QueueTable";
import { CaseDetailError } from "../components/StateNotices";
import { useAuth } from "../lib/auth";
import type { QueueCaseSummary } from "../lib/types";

export function CaseQueuePage() {
  const { user, signOut } = useAuth();
  const [cases, setCases] = useState<QueueCaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchQueue()
      .then((data) => {
        if (!cancelled) setCases(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Could not load the queue.");
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-[20px] text-[var(--color-text)]">Case queue</h1>
        <div className="flex items-center gap-3 text-[12px] text-[var(--color-text-muted)]">
          {user?.email && <span>{user.email}</span>}
          <button
            type="button"
            onClick={() => signOut()}
            className="border border-[var(--color-rule)] px-2 py-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            Sign out
          </button>
        </div>
      </div>

      {error && <CaseDetailError message={error} onRetry={() => setReloadToken((t) => t + 1)} />}

      {!error && cases === null && (
        <div className="text-[13px] text-[var(--color-text-faint)]">Loading queue...</div>
      )}

      {!error && cases !== null && cases.length === 0 && (
        <div className="border border-[var(--color-rule)] p-6 text-[13px] text-[var(--color-text-muted)]">
          No cases require review right now.
        </div>
      )}

      {!error && cases !== null && cases.length > 0 && <QueueTable cases={cases} />}
    </div>
  );
}
