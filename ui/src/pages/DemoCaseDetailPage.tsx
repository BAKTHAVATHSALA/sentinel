import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchDemoCase } from "../lib/demoApi";
import { DemoNavBar } from "../components/DemoNavBar";
import { CaseHeader } from "../components/CaseHeader";
import { InvestigationSummary } from "../components/InvestigationSummary";
import { PipelineStrip } from "../components/PipelineStrip";
import { ExhibitCard } from "../components/ExhibitCard";
import { FindingsPanel } from "../components/FindingsPanel";
import { CounterfactualPanel } from "../components/CounterfactualPanel";
import { PolicyLedgerEntry } from "../components/PolicyLedgerEntry";
import { CitationThreadProvider } from "../components/CitationThread";
import { DemoHumanDecisionPanel } from "../components/DemoHumanDecisionPanel";
import { DemoDecisionConfirmationScreen } from "../components/DecisionConfirmationScreen";
import { DecisionRecord } from "../components/DecisionRecord";
import {
  CaseDetailError,
  CaseUnavailableNotice,
  EmptyInvestigationNotice,
  LoadingSkeleton,
  PartialEvidenceBanner,
  ReasoningFailedNotice,
} from "../components/StateNotices";
import type { CaseDocument, DecisionResponse } from "../lib/types";

export function DemoCaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [caseDoc, setCaseDoc] = useState<CaseDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [counterfactualLoading, setCounterfactualLoading] = useState(false);
  const [counterfactualError, setCounterfactualError] = useState<string | null>(null);
  const [decisionResult, setDecisionResult] = useState<DecisionResponse | null>(null);

  const load = useCallback(() => {
    if (!caseId) return;
    fetchDemoCase(caseId)
      .then((data) => {
        setCaseDoc(data);
        setError(null);
        setErrorStatus(null);
      })
      .catch((e: any) => {
        setError(e.message ?? `Could not load demo case ${caseId}.`);
        setErrorStatus(e.status ?? null);
      });
  }, [caseId]);

  useEffect(() => {
    if (decisionResult) return;
    load();
  }, [load, reloadToken, decisionResult]);

  function requestCounterfactual(factId: string) {
    if (!caseId) return;
    setCounterfactualLoading(true);
    setCounterfactualError(null);
    fetchDemoCase(caseId, factId)
      .then(setCaseDoc)
      .catch((e: any) => setCounterfactualError(e.message ?? "Could not run live re-check."))
      .finally(() => setCounterfactualLoading(false));
  }

  if (decisionResult) {
    return (
      <div className="flex h-screen flex-col">
        <DemoNavBar onResetComplete={() => setDecisionResult(null)} />
        <DemoDecisionConfirmationScreen decision={decisionResult} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen flex-col">
        <DemoNavBar />
        {errorStatus === 404 ? (
          <CaseUnavailableNotice message={error} />
        ) : (
          <CaseDetailError message={error} onRetry={() => setReloadToken((t) => t + 1)} />
        )}
      </div>
    );
  }

  if (!caseDoc) {
    return (
      <div className="flex h-screen flex-col">
        <DemoNavBar />
        <LoadingSkeleton />
      </div>
    );
  }

  const exhibitNumbers: Record<string, number> = {};
  caseDoc.evidence_bundle?.facts.forEach((fact, i) => {
    exhibitNumbers[fact.fact_id] = i + 1;
  });

  const investigated = caseDoc.evidence_bundle !== null;

  return (
    <div className="flex flex-col">
      <div className="sticky top-0 z-10">
        <DemoNavBar onResetComplete={() => setReloadToken((t) => t + 1)} />
      </div>

      <div className="w-full px-6 py-4">
        <CitationThreadProvider>
          <div className="flex flex-col gap-4 pb-10">
            <CaseHeader caseDoc={caseDoc} />

            <PipelineStrip caseDoc={caseDoc} />

            {investigated && caseDoc.findings && <InvestigationSummary findings={caseDoc.findings} />}
            {!investigated && <EmptyInvestigationNotice state={caseDoc.state} />}

            {investigated && (
              <>
                {caseDoc.evidence_bundle!.completeness === "PARTIAL" && (
                  <PartialEvidenceBanner missing={caseDoc.evidence_bundle!.missing_required_evidence} />
                )}

                <section className="border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
                  <h2 className="mb-3 text-[13px] text-[var(--color-text-muted)]">Evidence</h2>
                  <div className="flex flex-col gap-3">
                    {caseDoc.evidence_bundle!.facts.map((fact, i) => (
                      <ExhibitCard
                        key={fact.fact_id}
                        fact={fact}
                        index={i}
                        excluded={fact.fact_id === caseDoc.counterfactual?.removed_fact_id}
                      />
                    ))}
                  </div>
                </section>

                {caseDoc.findings ? (
                  <FindingsPanel findings={caseDoc.findings} exhibitNumbers={exhibitNumbers} />
                ) : (
                  <ReasoningFailedNotice />
                )}

                <div className="border border-[var(--color-rule)] bg-[var(--color-surface)]">
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
                </div>
              </>
            )}

            {caseDoc.policy_decision && (
              <div className="border border-[var(--color-rule)] bg-[var(--color-surface)]">
                <PolicyLedgerEntry decision={caseDoc.policy_decision} />
              </div>
            )}

            {/* Human Decision Section */}
            <div className="border-t-2 border-[var(--color-caution)] bg-[var(--color-surface-raised)]">
              {caseDoc.state === "HUMAN_REVIEW" && (
                <DemoHumanDecisionPanel caseDoc={caseDoc} onDecided={setDecisionResult} />
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
    </div>
  );
}
