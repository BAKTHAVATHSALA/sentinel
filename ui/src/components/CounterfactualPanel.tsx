import { useState } from "react";
import { CompassGlyph } from "./icons";
import { SupportPillars } from "./SupportPillars";
import { CitationChip } from "./CitationChip";
import type { CaseFindings, CounterfactualResult, Fact, RobustnessResult } from "../lib/types";

/**
 * Robustness / counterfactual panel (design spec #10, signature interaction
 * #2). The fast-path estimate is real data from the case document, always
 * shown. The live re-check (mega-prompt Section 9/10) calls the real backend
 * -- GET /cases/{case_id}?simulate_without=<fact_id> -- which re-invokes
 * Gemini Reasoning for real on a reduced evidence bundle and reports whether
 * Policy's outcome would actually change; this is never persisted.
 */
export function CounterfactualPanel({
  robustness,
  findings,
  exhibitNumbers,
  facts,
  counterfactual,
  counterfactualLoading,
  counterfactualError,
  onRequestCounterfactual,
}: {
  robustness: RobustnessResult | null;
  findings: CaseFindings | null;
  exhibitNumbers: Record<string, number>;
  facts: Fact[];
  counterfactual?: CounterfactualResult;
  counterfactualLoading: boolean;
  counterfactualError: string | null;
  onRequestCounterfactual: (factId: string) => void;
}) {
  const [selectedFactId, setSelectedFactId] = useState("");

  return (
    <section className="border-b border-[var(--color-rule)] p-4">
      <header className="mb-3 flex items-center gap-2 text-[12px] text-[var(--color-text-muted)]">
        <CompassGlyph />
        <span>Robustness</span>
        <span className="text-[var(--color-text-faint)]">&middot; Advisory</span>
      </header>

      {robustness && findings ? (
        <SupportPillars robustness={robustness} findings={findings} exhibitNumbers={exhibitNumbers} />
      ) : (
        <p className="text-[12px] text-[var(--color-text-faint)]">Not scored -- no findings to evaluate.</p>
      )}

      {facts.length > 0 && (
        <div className="mt-3 border-t border-dashed border-[var(--color-rule)] pt-3">
          <label className="flex flex-col gap-1 text-[11px] text-[var(--color-text-faint)]">
            Remove a fact and re-check live
            <div className="flex gap-2">
              <select
                value={selectedFactId}
                onChange={(e) => setSelectedFactId(e.target.value)}
                className="min-w-0 flex-1 border border-[var(--color-rule)] bg-[var(--color-ground)] px-2 py-1 text-[12px] text-[var(--color-text)]"
              >
                <option value="">Select evidence&hellip;</option>
                {facts.map((fact) => (
                  <option key={fact.fact_id} value={fact.fact_id}>
                    Exhibit {exhibitNumbers[fact.fact_id] ?? "?"} &middot; {fact.type}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={!selectedFactId || counterfactualLoading}
                onClick={() => onRequestCounterfactual(selectedFactId)}
                className="border border-[var(--color-rule-strong)] px-2 py-1 text-[12px] text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {counterfactualLoading ? "Re-checking..." : "Run"}
              </button>
            </div>
          </label>

          {counterfactualError && <p className="mt-2 text-[12px] text-[var(--color-critical)]">{counterfactualError}</p>}

          {counterfactual && (
            <div className="mt-3 border border-[var(--color-rule-strong)] p-2">
              <p className="text-[11px] text-[var(--color-text-faint)]">
                Without{" "}
                <CitationChip factIds={[counterfactual.removed_fact_id]} exhibitNumbers={exhibitNumbers} />:
              </p>
              <p className="mt-1 text-[13px] text-[var(--color-text)]">
                {counterfactual.robustness.classification === "FRAGILE" ? "Fragile" : "Robust"}
                {counterfactual.findings && <> &middot; risk assessment: {counterfactual.findings.risk_assessment}</>}
              </p>
              <p
                className="mt-1 text-[12px]"
                style={{
                  color: counterfactual.policy_outcome_would_change
                    ? "var(--color-caution)"
                    : "var(--color-text-muted)",
                }}
              >
                {counterfactual.policy_outcome_would_change
                  ? "The policy outcome would change without this fact."
                  : "The policy outcome would not change without this fact."}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
