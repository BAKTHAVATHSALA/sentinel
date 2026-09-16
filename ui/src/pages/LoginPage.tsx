import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

/** Firebase email/password sign-in (V1 Authoritative Ruling Part 1). Keeps the
 * existing Evidence Ledger design system's restrained, functional visual
 * language -- no redesign, this is a new screen built to match it. */
export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await signIn(email.trim(), password);
      navigate("/", { replace: true });
    } catch {
      setError("Could not sign in. Check your email and password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-[var(--color-ground)]">
      <form
        onSubmit={handleSubmit}
        className="flex w-[320px] flex-col gap-3 border border-[var(--color-rule)] bg-[var(--color-surface)] p-6"
      >
        <h1 className="mb-1 text-[16px] text-[var(--color-text)]">Sentinel</h1>
        <p className="mb-2 text-[12px] text-[var(--color-text-muted)]">Sign in to review cases.</p>

        <label className="flex flex-col gap-1 text-[12px] text-[var(--color-text-muted)]">
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            required
            className="border border-[var(--color-rule)] bg-[var(--color-ground)] px-2 py-1 text-[13px] text-[var(--color-text)]"
          />
        </label>

        <label className="flex flex-col gap-1 text-[12px] text-[var(--color-text-muted)]">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            className="border border-[var(--color-rule)] bg-[var(--color-ground)] px-2 py-1 text-[13px] text-[var(--color-text)]"
          />
        </label>

        {error && <div className="text-[12px] text-[var(--color-critical)]">{error}</div>}

        <button
          type="submit"
          disabled={submitting}
          className="mt-1 border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-3 py-2 text-[13px] text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
