import { useState } from "react";
import { CompassGlyph } from "./icons";
import { SupportPillars } from "./SupportPillars";
import { CitationChip } from "./CitationChip";
import type { CaseFindings, CounterfactualResult, Fact, FindingFactor, RobustnessResult } from "../lib/types";

const DISPOSITION_LABELS: Record<string, string> = {
  CLEAR: "Clear",
  ESCALATE: "Escalate",
  BLOCK_HOLD: "Block & hold",
};

/**
 * Robustness / counterfactual panel (design spec #10, signature interaction
 * #2). The fast-path estimate is real data from the case document, always
 * shown. The live re-check calls the real backend -- GET
 * /cases/{case_id}?simulate_without=<fact_id> -- which re-invokes Gemini
 * Reasoning for real on a reduced evidence bundle and reports whether
 * Policy's outcome would actually change; this is never persisted, and the
 * original findings rendered elsewhere on the page are never touched by it.
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
                disabled={counterfactualLoading}
                className="min-w-0 flex-1 border border-[var(--color-rule)] bg-[var(--color-ground)] px-2 py-1 text-[12px] text-[var(--color-text)] disabled:opacity-60"
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
                {counterfactualLoading ? "Re-running investigation..." : "Run"}
              </button>
            </div>
          </label>

          {counterfactualError && (
            <div className="mt-3 border border-[var(--color-critical)] bg-[var(--color-critical-soft)] p-2">
              <p className="text-[12px] text-[var(--color-critical)]">{counterfactualError}</p>
              <button
                type="button"
                onClick={() => onRequestCounterfactual(selectedFactId)}
                className="mt-2 border border-[var(--color-critical)] px-2 py-1 text-[11px] text-[var(--color-critical)]"
              >
                Try again
              </button>
            </div>
          )}

          {counterfactual && !counterfactualLoading && (
            <CounterfactualResultCard counterfactual={counterfactual} exhibitNumbers={exhibitNumbers} />
          )}
        </div>
      )}
    </section>
  );
}

function CounterfactualResultCard({
  counterfactual,
  exhibitNumbers,
}: {
  counterfactual: CounterfactualResult;
  exhibitNumbers: Record<string, number>;
}) {
  const removedId = counterfactual.removed_fact_id;
  const findings = counterfactual.findings;
  // Defensive: never present the removed fact as if it were still supporting
  // evidence -- Gemini never saw it, so this only guards against an edge case.
  const excludeRemoved = (ids: string[]) => ids.filter((id) => id !== removedId);
  const supportingFactors = (findings?.supporting_factors ?? [])
    .map((f) => ({ ...f, fact_ids: excludeRemoved(f.fact_ids) }))
    .filter((f) => f.statement);
  const counterFactors = (findings?.counter_factors ?? [])
    .map((f) => ({ ...f, fact_ids: excludeRemoved(f.fact_ids) }))
    .filter((f) => f.statement);
  const citations = (findings?.evidence_citations ?? [])
    .map((c) => ({ ...c, fact_ids: excludeRemoved(c.fact_ids) }))
    .filter((c) => c.fact_ids.length > 0);

  return (
    <div className="mt-3 border border-[var(--color-caution)] bg-[var(--color-caution-soft)] p-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold tracking-wide text-[var(--color-caution)]">
          LIVE COUNTERFACTUAL SIMULATION
        </span>
      </div>
      <p className="mt-1 text-[11px] text-[var(--color-text-muted)]">
        This simulation removes one evidence fact and re-runs the investigation. The persisted case is unchanged.
      </p>

      <p className="mt-2 text-[12px] text-[var(--color-text)]">
        Removed: <CitationChip factIds={[removedId]} exhibitNumbers={exhibitNumbers} />
      </p>

      {findings ? (
        <div className="mt-2 flex flex-col gap-2 border-t border-dashed border-[var(--color-caution)] pt-2">
          <Row label="Risk assessment" value={findings.risk_assessment} />
          <Row
            label="AI advisory disposition"
            value={DISPOSITION_LABELS[findings.recommended_disposition] ?? findings.recommended_disposition}
            hint="Advisory only -- not the final decision"
          />
          <Row
            label="Robustness"
            value={counterfactual.robustness.classification === "FRAGILE" ? "Fragile" : "Robust"}
          />
          {/* Fragility, not failure: this reports a live counterfactual finding
              (the same concept SupportPillars colors amber as "Fragile"), never
              an actual error -- amber keeps that distinction consistent app-wide. */}
          <p
            className="text-[12px]"
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

          {supportingFactors.length > 0 && (
            <FactorList title="Remaining supporting factors" factors={supportingFactors} exhibitNumbers={exhibitNumbers} />
          )}
          {counterFactors.length > 0 && (
            <FactorList title="Remaining counter factors" factors={counterFactors} exhibitNumbers={exhibitNumbers} />
          )}
          {citations.length > 0 && (
            <div>
              <div className="mb-1 text-[11px] text-[var(--color-text-faint)]">Remaining citations</div>
              <div className="flex flex-wrap gap-1.5">
                {citations.map((c) => (
                  <CitationChip key={c.claim_id} factIds={c.fact_ids} exhibitNumbers={exhibitNumbers} />
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="mt-2 border-t border-dashed border-[var(--color-caution)] pt-2 text-[12px] text-[var(--color-text-muted)]">
          Reasoning could not produce a valid assessment without this fact.
        </p>
      )}
    </div>
  );
}

function Row({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="text-[12px]">
      <span className="text-[var(--color-text-faint)]">{label}: </span>
      <span className="text-[var(--color-text)]">{value}</span>
      {hint && <span className="ml-1 text-[11px] text-[var(--color-text-faint)]">({hint})</span>}
    </div>
  );
}

function FactorList({
  title,
  factors,
  exhibitNumbers,
}: {
  title: string;
  factors: FindingFactor[];
  exhibitNumbers: Record<string, number>;
}) {
  return (
    <div>
      <div className="mb-1 text-[11px] text-[var(--color-text-faint)]">{title}</div>
      <ul className="flex flex-col gap-1.5">
        {factors.map((factor) => (
          <li key={factor.statement} className="flex flex-wrap items-start gap-1.5 text-[12px] text-[var(--color-text-muted)]">
            <span className="rounded-[3px] border border-[var(--color-rule-strong)] px-1 py-0.5 text-[10px] text-[var(--color-text-faint)]">
              {factor.materiality}
            </span>
            <span className="max-w-[44ch] leading-[1.4]">{factor.statement}</span>
            {factor.fact_ids.length > 0 && <CitationChip factIds={factor.fact_ids} exhibitNumbers={exhibitNumbers} />}
          </li>
        ))}
      </ul>
    </div>
  );
}
