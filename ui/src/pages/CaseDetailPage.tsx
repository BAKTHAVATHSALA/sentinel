import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchCase, ApiError } from "../lib/api";
import { AnalystNavBar } from "../components/AnalystNavBar";
import { CaseHeader } from "../components/CaseHeader";
import { InvestigationSummary } from "../components/InvestigationSummary";
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

/**
 * Progressive-disclosure case page (UX polish pass). Page order, top to
 * bottom: Case Header -> Investigation Pipeline -> Investigation Summary ->
 * Evidence -> Gemini Assessment -> Robustness -> Policy -> Human Decision.
 * The pipeline comes immediately after the header because it represents the
 * case's lifecycle (CASE -> WHERE IS IT? -> WHAT DID IT FIND? -> EVIDENCE ->
 * WHAT ACTION CAN I TAKE?) -- an analyst should see where the case stands
 * before reading what was found. Uses the full available desktop width
 * (only comfortable side padding, no max-width cap) so evidence cards and
 * the pipeline strip both get real room. No data, endpoint, or decision
 * logic changed, only how the same real fields are arranged and worded.
 *
 * Layout note (content-driven height, single scroll owner): the main
 * content branch below deliberately does NOT use `h-screen` +
 * `flex-1 overflow-y-auto` the way the loading/error/confirmation branches
 * still do. That combination forces the content region to be exactly one
 * viewport tall regardless of actual content -- once evidence/Gemini/
 * robustness/policy are collapsed by default (progressive disclosure), real
 * content is often *shorter* than the viewport, leaving a large forced-empty
 * region below Human Decision, and the fixed-height nested scroll box can
 * also produce a second, browser-level scrollbar alongside its own. The
 * page now flows naturally (its own height, whatever that is) and scrolls
 * at the document level -- one scroll owner, no artificial floor or cap.
 * The nav bar is pinned with `sticky` (not the old `h-screen` trick) so it
 * still stays visible while the page scrolls.
 */
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
    <div className="flex flex-col">
      <div className="sticky top-0 z-10">
        <AnalystNavBar />
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

            {/* Human Decision: deliberately the most visually distinct section on the
                page -- a raised surface + accent top border -- so the analyst's own
                action area is never confused with the read-only investigation record
                above it. No permission/disabled-state logic changes here at all. */}
            <div className="border-t-2 border-[var(--color-caution)] bg-[var(--color-surface-raised)]">
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
    </div>
  );
}
