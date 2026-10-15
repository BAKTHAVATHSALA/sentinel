import { Link } from "react-router-dom";
import { InvestigationJourney, type JourneyPhase } from "./InvestigationJourney";
import { AnomalyTagChip } from "./AnomalyTagChip";
import type { DecisionSummary, Transaction, TransactionInvestigationResult, TransactionLiveStatus } from "../lib/types";

/**
 * Renders exactly what POST /transactions returned -- nothing more. The
 * Transaction Console never calls GET /cases/{case_id}, so protected case
 * content (raw evidence facts, Gemini findings text/citations, robustness
 * detail, exact merchant financial figures, analyst email/UID) is never
 * available here and never shown; `decision_summary` is the backend's own
 * curated, public-safe distillation of the real pipeline result (see
 * shared/pipeline/orchestrator.py:_decision_summary). Full per-stage detail
 * remains the separate, authenticated Analyst Portal's job (CaseDetailPage)
 * once the assigned analyst signs in.
 *
 * The UI branches ONLY on the real final `state` (AUTO_RESOLVED vs.
 * HUMAN_REVIEW) -- never on risk_assessment -- and the two dispositions
 * render from completely separate functions below with zero shared "why"
 * content, specifically so an AUTO_RESOLVED explanation can never bleed
 * into a HUMAN_REVIEW result or vice versa.
 */
export function InvestigationResultPanel({
  phase,
  result,
  transaction,
  liveStatus,
}: {
  phase: JourneyPhase;
  result: TransactionInvestigationResult | null;
  transaction: Transaction;
  liveStatus?: TransactionLiveStatus | null;
}) {
  const label =
    result?.state === "HUMAN_REVIEW" ? "HUMAN REVIEW" : result?.state === "AUTO_RESOLVED" ? "AUTO-RESOLVED" : result?.state;
  const bannerStyle =
    result?.state === "HUMAN_REVIEW"
      ? "border-[var(--color-caution)] bg-[var(--color-caution-soft)] text-[var(--color-caution)]"
      : result?.state === "AUTO_RESOLVED"
        ? "border-[var(--color-stable)] bg-[var(--color-stable-soft)] text-[var(--color-stable)]"
        : "border-[var(--color-rule)] bg-[var(--color-surface-raised)] text-[var(--color-text)]";

  return (
    <div className="flex flex-col gap-5 border border-[var(--color-rule)] bg-[var(--color-surface)] p-5">
      {result?.duplicate && (
        <div className="border border-[var(--color-caution)] bg-[var(--color-caution-soft)] p-2 text-[12px] text-[var(--color-caution)]">
          This transaction_id was already submitted -- showing its existing case, not a new investigation.
        </div>
      )}

      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[13px] text-[var(--color-text)]">
        <span className="font-mono text-[var(--color-text-muted)]">{transaction.transaction_id}</span>
        <span className="text-[15px]">
          {transaction.currency} {transaction.amount}
        </span>
        <span className="text-[var(--color-text-muted)]">{transaction.merchant_category}</span>
        <span className="text-[var(--color-text-muted)]">
          {transaction.channel} &middot; {transaction.authorization_stage}
        </span>
      </div>

      <div className="overflow-x-auto py-1">
        <InvestigationJourney phase={phase} result={result} liveStatus={liveStatus} />
      </div>

      {phase === "running" && (
        <p className="text-[13px] text-[var(--color-text-muted)]">Investigating transaction...</p>
      )}

      {phase === "done" && result && (
        <div className={`border p-4 ${bannerStyle}`}>
          <p className="text-[22px] tracking-tight">{label}</p>

          {result.state === "AUTO_RESOLVED" && <AutoResolvedExplanation />}

          {result.state === "HUMAN_REVIEW" && (
            <>
              <HumanReviewExplanation summary={result.decision_summary} />

              <p className="mt-3 text-[12px] text-[var(--color-text-muted)]">
                Case: <span className="font-mono">{result.case_id}</span>
              </p>

              {result.assignment ? (
                <div className="mt-3 border-t border-[var(--color-rule)] pt-3">
                  <p className="text-[12px] text-[var(--color-text-muted)]">Assigned to:</p>
                  <p className="text-[14px] text-[var(--color-text)]">{result.assignment.analyst_name}</p>
                </div>
              ) : (
                <p className="mt-3 border-t border-[var(--color-rule)] pt-3 text-[13px] text-[var(--color-text-muted)]">
                  No analyst is currently available.
                </p>
              )}

              {/* Primary next step for HUMAN_REVIEW: demonstrate the protected
                  analyst investigation. For demo cases, opens the demo sandbox;
                  for production cases, requires Firebase login. */}
              <Link
                to={caseLink(result, transaction)}
                className="mt-4 inline-block border border-[var(--color-rule-strong)] bg-[var(--color-surface-raised)] px-4 py-2 text-[13px] text-[var(--color-text)] hover:border-[var(--color-text-muted)]"
              >
                Open Case
              </Link>
            </>
          )}

          {result.state !== "AUTO_RESOLVED" && result.state !== "HUMAN_REVIEW" && (
            <>
              <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
                Case: <span className="font-mono">{result.case_id}</span>
              </p>
              <Link
                to={caseLink(result, transaction)}
                className="mt-3 inline-block border border-[var(--color-rule)] px-3 py-1.5 text-[13px] text-[var(--color-text)] hover:border-[var(--color-rule-strong)]"
              >
                Open Case
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** Demo transactions open the Demo Analyst queue (pre-seeded demo cases),
 * regardless of who the pipeline assigned; real cases open the analyst portal. */
function caseLink(result: TransactionInvestigationResult, transaction: Transaction): string {
  const isDemo = result.case_id.startsWith("demo_") || transaction.transaction_id.startsWith("tx_demo_");
  return isDemo ? "/demo" : `/case/${encodeURIComponent(result.case_id)}`;
}

function ChecklistItem({ children }: { children: string }) {
  return (
    <li className="flex items-baseline gap-1.5">
      <span aria-hidden="true" className="text-[var(--color-stable)]">
        &#10003;
      </span>
      {children}
    </li>
  );
}

/**
 * AUTO_RESOLVED-only content. Deliberately has NO access to risk_assessment
 * at all (it isn't even passed in) -- a clean result must never prominently
 * display a risk label, and this makes that structurally impossible rather
 * than merely a styling choice. Every bullet here is unconditionally true
 * whenever `state === "AUTO_RESOLVED"`: reaching this state itself proves
 * Detection ran, found zero anomaly tags, and risk was LOW (Rule P-004 /
 * shared/pipeline/orchestrator.py:_resolve_clean_transaction) -- there is
 * no field-by-field gating needed because the disposition already implies
 * these facts.
 */
function AutoResolvedExplanation() {
  return (
    <>
      <p className="mt-1 text-[13px] text-[var(--color-text-muted)]">No anomalies found</p>
      <p className="text-[13px] text-[var(--color-text-muted)]">No analyst action required.</p>
      <ul className="mt-3 flex flex-col gap-0.5 border-t border-[var(--color-rule)] pt-3 text-[12px] text-[var(--color-text)]">
        <ChecklistItem>No anomaly signals detected.</ChecklistItem>
        <ChecklistItem>Required automated investigation checks completed.</ChecklistItem>
        <ChecklistItem>No analyst action required.</ChecklistItem>
      </ul>
    </>
  );
}

/**
 * HUMAN_REVIEW-only content. Never renders "Why this was resolved",
 * "automatic resolution", "No analyst action required", or any other
 * AUTO_RESOLVED copy -- this function and AutoResolvedExplanation above
 * share no code and no strings, so the two can't cross-contaminate.
 */
function HumanReviewExplanation({ summary }: { summary: DecisionSummary }) {
  const isClean = summary.anomaly_tags.length === 0;
  // A HUMAN_REVIEW case can legitimately have never been investigated: a
  // CLEAN (zero anomaly tag) transaction whose risk_band was still MEDIUM/HIGH
  // skips Evidence/Reasoning entirely, same as a LOW-risk clean transaction
  // does (shared/pipeline/orchestrator.py:_escalate_clean_transaction_with_elevated_risk)
  // -- evidence_completeness stays null in that case, so "Evidence collected"
  // / "AI reasoning complete" must not be claimed for it.
  const investigated = summary.evidence_completeness !== null;

  return (
    <>
      {summary.risk_assessment && (
        <p className="mt-1 text-[13px] font-medium text-[var(--color-text)]">{summary.risk_assessment} RISK</p>
      )}
      <p className="text-[13px] text-[var(--color-text-muted)]">Analyst investigation required.</p>

      <div className="mt-3 flex flex-col gap-3 border-t border-[var(--color-rule)] pt-3">
        {summary.anomaly_tags.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] text-[var(--color-text-muted)]">Signals:</span>
            <div className="flex flex-wrap items-center gap-1.5">
              {summary.anomaly_tags.map((tag) => (
                <AnomalyTagChip key={tag} tag={tag} />
              ))}
            </div>
          </div>
        ) : (
          <p className="text-[12px] text-[var(--color-text-muted)]">
            No anomaly signals were detected, but the risk assessment still required analyst review.
          </p>
        )}

        {summary.merchant_flagged && (
          <p className="text-[12px] text-[var(--color-caution)]">Merchant flagged as elevated risk.</p>
        )}

        <div>
          <p className="text-[12px] text-[var(--color-text-muted)]">Investigation status:</p>
          <ul className="mt-1 flex flex-col gap-0.5 text-[12px] text-[var(--color-text)]">
            <ChecklistItem>Detection complete</ChecklistItem>
            {investigated && (
              <>
                <ChecklistItem>Evidence collected</ChecklistItem>
                <ChecklistItem>AI reasoning complete</ChecklistItem>
              </>
            )}
            <ChecklistItem>Routed for human review</ChecklistItem>
          </ul>
        </div>

        {!isClean && (
          <p className="text-[12px] text-[var(--color-text-muted)]">
            Risk signals were detected and the case requires analyst judgment.
          </p>
        )}
      </div>
    </>
  );
}
