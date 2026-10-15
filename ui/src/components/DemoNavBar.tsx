import { useState } from "react";
import { Link } from "react-router-dom";
import { resetDemoSession } from "../lib/demoApi";

export function DemoNavBar({ onResetComplete }: { onResetComplete?: () => void }) {
  const [resetting, setResetting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleReset() {
    if (resetting) return;
    setResetting(true);
    setMessage(null);
    try {
      await resetDemoSession();
      setMessage("Demo dataset restored.");
      if (onResetComplete) {
        onResetComplete();
      }
      setTimeout(() => setMessage(null), 3000);
    } catch (e: any) {
      setMessage(e.message || "Failed to reset demo.");
      setTimeout(() => setMessage(null), 4000);
    } finally {
      setResetting(false);
    }
  }

  return (
    <nav className="flex items-center justify-between border-b border-[var(--color-rule)] bg-[var(--color-surface)] px-4 py-2">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-[13px] tracking-wide text-[var(--color-text-faint)]">SENTINEL</span>
          <span className="rounded bg-[var(--color-caution-soft)] px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-[var(--color-caution)]">
            DEMO MODE
          </span>
        </div>
        <Link to="/investigate" className="text-[13px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          Transaction Console
        </Link>
      </div>

      <div className="flex items-center gap-4 text-[12px] text-[var(--color-text-muted)]">
        {message && (
          <span className="text-[11px] text-[var(--color-stable)] transition-opacity">
            {message}
          </span>
        )}
        <div className="flex items-center gap-1.5">
          <span className="text-[var(--color-text)] font-medium">Demo Analyst</span>
          <span className="text-[var(--color-text-faint)]">(Analyst)</span>
        </div>
        <button
          type="button"
          onClick={handleReset}
          disabled={resetting}
          className="border border-[var(--color-caution)] bg-[var(--color-caution-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--color-caution)] hover:bg-[var(--color-surface-raised)] disabled:opacity-50"
        >
          {resetting ? "Resetting..." : "Reset Demo"}
        </button>
      </div>
    </nav>
  );
}
