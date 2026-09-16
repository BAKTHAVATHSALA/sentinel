import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchCase, ApiError } from "../lib/api";
import { CaseSpine } from "../components/CaseSpine";
import { PipelineStrip } from "../components/PipelineStrip";
import { ExhibitCard } from "../components/ExhibitCard";
import { FindingsPanel } from "../components/FindingsPanel";
import { CounterfactualPanel } from "../components/CounterfactualPanel";
import { PolicyLedgerEntry } from "../components/PolicyLedgerEntry";
import { HumanDecisionPanel } from "../components/HumanDecisionPanel";
import { DecisionRecord } from "../components/DecisionRecord";
import { CitationThreadProvider } from "../components/CitationThread";
import {
  CaseDetailError,
  EmptyInvestigationNotice,
  LoadingSkeleton,
  PartialEvidenceBanner,
  ReasoningFailedNotice,
} from "../components/StateNotices";
import type { CaseDocument } from "../lib/types";

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [caseDoc, setCaseDoc] = useState<CaseDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [counterfactualLoading, setCounterfactualLoading] = useState(false);
  const [counterfactualError, setCounterfactualError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!caseId) return;
    setError(null);
    fetchCase(caseId)
      .then(setCaseDoc)
      .catch((e) => setError(e instanceof ApiError ? e.message : `Could not load case ${caseId}.`));
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load, reloadToken]);

  function requestCounterfactual(factId: string) {
    if (!caseId) return;
    setCounterfactualLoading(true);
    setCounterfactualError(null);
    fetchCase(caseId, factId)
      .then(setCaseDoc)
      .catch((e) => setCounterfactualError(e instanceof ApiError ? e.message : "Could not run the live re-check."))
      .finally(() => setCounterfactualLoading(false));
  }

  if (error) return <CaseDetailError message={error} onRetry={() => setReloadToken((t) => t + 1)} />;
  if (!caseDoc) return <LoadingSkeleton />;

  const exhibitNumbers: Record<string, number> = {};
  caseDoc.evidence_bundle?.facts.forEach((fact, i) => {
    exhibitNumbers[fact.fact_id] = i + 1;
  });

  const investigated = caseDoc.evidence_bundle !== null;

  return (
    <div className="flex h-screen flex-col">
      <div className="border-b border-[var(--color-rule)] px-4 py-2">
        <Link to="/" className="text-[12px] text-[var(--color-text-muted)]">
          &larr; Case queue
        </Link>
      </div>

      <div className="px-4 pt-4">
        <PipelineStrip caseDoc={caseDoc} />
      </div>

      <CitationThreadProvider>
        <div className="flex min-h-0 flex-1 overflow-hidden">
          <div className="overflow-y-auto">
            <CaseSpine caseDoc={caseDoc} />
          </div>

          <div className="min-w-[560px] flex-1 overflow-y-auto">
            {!investigated ? (
              <EmptyInvestigationNotice />
            ) : (
              <>
                {caseDoc.evidence_bundle!.completeness === "PARTIAL" && (
                  <div className="p-4">
                    <PartialEvidenceBanner missing={caseDoc.evidence_bundle!.missing_required_evidence} />
                  </div>
                )}

                <div className="flex flex-col gap-3 p-4">
                  <h2 className="text-[13px] text-[var(--color-text-muted)]">Evidence</h2>
                  {caseDoc.evidence_bundle!.facts.map((fact, i) => (
                    <ExhibitCard key={fact.fact_id} fact={fact} index={i} />
                  ))}
                </div>

                {caseDoc.findings ? (
                  <FindingsPanel findings={caseDoc.findings} exhibitNumbers={exhibitNumbers} />
                ) : (
                  <div className="p-4">
                    <ReasoningFailedNotice />
                  </div>
                )}
              </>
            )}
          </div>

          <div className="w-[340px] min-w-[300px] max-w-[380px] overflow-y-auto border-l border-[var(--color-rule)]">
            {investigated && (
              <CounterfactualPanel
                robustness={caseDoc.robustness}
                findings={caseDoc.findings}
                exhibitNumbers={exhibitNumbers}
                facts={caseDoc.evidence_bundle?.facts ?? []}
                counterfactual={caseDoc.counterfactual}
                counterfactualLoading={counterfactualLoading}
                counterfactualError={counterfactualError}
                onRequestCounterfactual={requestCounterfactual}
              />
            )}
            {caseDoc.policy_decision && <PolicyLedgerEntry decision={caseDoc.policy_decision} />}
            {caseDoc.state === "HUMAN_REVIEW" && (
              <HumanDecisionPanel caseDoc={caseDoc} onDecided={() => setReloadToken((t) => t + 1)} />
            )}
            {caseDoc.state === "FINALIZED" && <DecisionRecord caseDoc={caseDoc} />}
            {caseDoc.state === "AUTO_RESOLVED" && (
              <div className="p-4 text-[13px] text-[var(--color-text-muted)]">
                No human action required &mdash; resolved automatically.
              </div>
            )}
          </div>
        </div>
      </CitationThreadProvider>
    </div>
  );
}
