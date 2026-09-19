import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchCase, ApiError } from "../lib/api";
import { AnalystNavBar } from "../components/AnalystNavBar";
import { CaseSpine } from "../components/CaseSpine";
import { PipelineStrip } from "../components/PipelineStrip";
import { ExhibitCard } from "../components/ExhibitCard";
import { FindingsPanel } from "../components/FindingsPanel";
import { CounterfactualPanel } from "../components/CounterfactualPanel";
import { PolicyLedgerEntry } from "../components/PolicyLedgerEntry";
import { HumanDecisionPanel } from "../components/HumanDecisionPanel";
import { DecisionConfirmationScreen } from "../components/DecisionConfirmationScreen";
import { DecisionRecord } from "../components/DecisionRecord";
import { CitationThreadProvider } from "../components/CitationThread";
import {
  CaseDetailError,
  CaseUnavailableNotice,
  EmptyInvestigationNotice,
  LoadingSkeleton,
  PartialEvidenceBanner,
  ReasoningFailedNotice,
} from "../components/StateNotices";
import type { CaseDocument, DecisionResponse } from "../lib/types";

export function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [caseDoc, setCaseDoc] = useState<CaseDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [counterfactualLoading, setCounterfactualLoading] = useState(false);
  const [counterfactualError, setCounterfactualError] = useState<string | null>(null);
  // Set only from a just-succeeded POST /cases/{case_id}/decision response.
  // While this is non-null, the page renders the confirmation screen built
  // from it and never calls fetchCase again -- critical for ESCALATE_SENIOR,
  // where a refetch would immediately (and correctly) fail the ownership
  // check the caller just gave up.
  const [decisionResult, setDecisionResult] = useState<DecisionResponse | null>(null);

  const load = useCallback(() => {
    if (!caseId) return;
    setError(null);
    setErrorStatus(null);
    fetchCase(caseId)
      .then(setCaseDoc)
      .catch((e) => {
        setError(e instanceof ApiError ? e.message : `Could not load case ${caseId}.`);
        setErrorStatus(e instanceof ApiError ? e.status : null);
      });
  }, [caseId]);

  useEffect(() => {
    if (decisionResult) return; // never refetch once a decision has been confirmed
    load();
  }, [load, reloadToken, decisionResult]);

  function requestCounterfactual(factId: string) {
    if (!caseId) return;
    setCounterfactualLoading(true);
    setCounterfactualError(null);
    fetchCase(caseId, factId)
      .then(setCaseDoc)
      .catch((e) => setCounterfactualError(e instanceof ApiError ? e.message : "Could not run the live re-check."))
      .finally(() => setCounterfactualLoading(false));
  }

  if (decisionResult) {
    return (
      <div className="flex h-screen flex-col">
        <AnalystNavBar />
        <DecisionConfirmationScreen decision={decisionResult} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen flex-col">
        <AnalystNavBar />
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
        <AnalystNavBar />
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
    <div className="flex h-screen flex-col">
      <AnalystNavBar />

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
              <EmptyInvestigationNotice state={caseDoc.state} />
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
                    <ExhibitCard
                      key={fact.fact_id}
                      fact={fact}
                      index={i}
                      excluded={fact.fact_id === caseDoc.counterfactual?.removed_fact_id}
                    />
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
            {caseDoc.state === "HUMAN_REVIEW" && <HumanDecisionPanel caseDoc={caseDoc} onDecided={setDecisionResult} />}
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
