---
name: sentinel-engineering
description: Use when building, reviewing, checking off checklist items, deciding what to do next, or committing in the Sentinel repo (services/, shared/, ui/, eval/, data/, scripts/, tests/) — enforces the Phase 0-6 build order, evidence-before-complete, the frozen v1.1 architecture, and the frozen v1.2 contracts.
---

# Sentinel Engineering

## Overview

Sentinel is built to one governing safety principle, frozen in
`Sentinel_Technical_Design_Contracts_v1_2_V1_SCOPE_ALIGNED.md`:

> Probabilistic AI investigates and reasons. Deterministic policy controls
> automated disposition. Humans retain authority over blocking and overrides.

Everything in this skill exists to keep that principle true while the build
proceeds through a fixed phase order under deadline pressure. The failure
mode this skill defends against is not incompetence — it's a competent agent
under time pressure deciding a shortcut is reasonable *this once*.

**Violating the letter of the phase order, the evidence rule, or the frozen
contracts is violating the spirit of the whole safety design.** There is no
version of "the checklist item isn't done but I'm confident it works" that is
acceptable here.

## Source of truth — read the files, don't rely on memory

**Authority hierarchy.** These three documents are not interchangeable and do
not carry equal weight. Use each one for what it governs, in this order:

1. `Sentinel_V1_Build_Architecture_v1.1.md` — **architecture.** What gets
   built: services, modules, datastores, topology.
2. `Sentinel_Technical_Design_Contracts_v1_2_V1_SCOPE_ALIGNED.md` — **frozen
   contracts, behavior, and safety invariants.** How every module must
   behave: exact shapes, the 10 Safety Invariants (§32), the Mandatory
   Policy Rules (§20), the Build/Don't-Build boundary (§34).
3. `Sentinel_V1_Build_Checklist.pdf` — **implementation sequence and
   completion evidence.** What task is currently authorized to be worked on,
   in what order, and what evidence marks it done.

**Never use the checklist to redefine architecture or contracts.** The
checklist sequences and gates work — it does not define what's true about
the system. If the checklist's wording ever seems to imply a different
scope, behavior, or shape than Architecture or Contracts, Architecture and
Contracts win for *what* and *how*; the checklist still governs *when* and
*what's authorized right now*.

| Document | Governs | How to consult |
|---|---|---|
| `Sentinel_V1_Build_Architecture_v1.1.md` | **Locked V1 architecture**: one Cloud Run service, in-process modules, Firestore-only (no Pub/Sub, BigQuery, or Vector Search/RAG in V1), CNP pre-auth scope only. | Cross-check before adding any service, queue, or datastore. |
| `Sentinel_Technical_Design_Contracts_v1_2_V1_SCOPE_ALIGNED.md` | **Contract shapes + the 10 frozen Safety Invariants (§32) + the Mandatory Policy Rules (§20) + the Build/Don't-Build boundary (§34).** Supersedes the v1.1 Contracts doc — that document is retired, do not consult or cite it. | Code must import these shapes from `shared/contracts/`, never redefine them ad hoc. |
| `Sentinel_V1_Build_Checklist.pdf` | **What to build and in what order.** The single source of truth for phase/task sequencing and exit criteria. | Read it directly with the Read tool (it supports PDF + a `pages` range). Page map: p.1 cover, p.2 Phase 0, p.3 Phase 1, p.4 Phase 2, p.5 Phase 3, p.6 Phase 4, p.7 Phase 5, p.8 Phase 6. Never paraphrase an item from memory — re-read the relevant page before checking or unchecking anything. |

**If any two of these documents conflict, STOP and surface the conflict to
the user in one sentence — do not silently choose one.** This applies in
both directions: don't let the checklist quietly narrow or widen what
Architecture/Contracts define, and don't assume a checklist phrasing that
sounds like scope is actually authoritative over either frozen document.
(The v1.1→v1.2 Contracts revision itself resolved the previous known
conflict — v1.1 described Pub/Sub/BigQuery/Vector-Search sections that
neither Architecture nor the checklist ever built; v1.2 removed them so all
three documents are now in sync. If a *new* discrepancy surfaces, treat it
the same way: name it, don't build past it.)

## Non-negotiable invariants

From Contracts §32 ("Safety Invariants — FINAL"), restated because they are
the actual test of "did this change break Sentinel," not a style preference:

1. Gemini cannot directly execute an action.
2. Policy cannot produce `BLOCK_HOLD`.
3. Policy cannot produce `AUTO_DECLINE`.
4. Only a human analyst can execute `BLOCK_HOLD`.
5. Partial required evidence cannot auto-resolve.
6. Every automated Policy decision records `rule_id` + `rule_version`.
7. Every material reasoning factor is traceable to evidence (a `fact_id`).
8. Duplicate request delivery cannot create duplicate side effects or cases.
9. Duplicate case creation for the same `transaction_id` is prevented.
10. A request that exhausts its bounded retries (tool failure, Gemini
    failure, malformed output) fails safe to `ESCALATE` within that same
    request — it never silently drops or auto-resolves.

Search the codebase for the literal strings `BLOCK_HOLD` and `AUTO_DECLINE`
outside `shared/contracts` and the human-decision endpoint whenever Policy
code changes — their appearance anywhere else is a defect, not a style
issue.

**Don't build** (Contracts §34, don't re-derive this from first principles —
it's already decided): other payment rails (UPI, IMPS/NEFT/RTGS, ATM,
incoming-side fraud), the `IMPOSSIBLE_TRAVEL` / `UNUSUAL_TIME` anomaly tags,
RAG / precedent retrieval / Vertex AI Vector Search, BigQuery, a Pub/Sub
event backbone (topics, DLQs, scheduled sweeps), multi-service topology or
per-service service accounts, a standalone synthetic-transaction-generator
*service*, a graph database, real KYC/merchant API integrations, a custom
fine-tuned Gemini model, a custom GNN, autonomous policy learning,
multi-tenant SaaS scaffolding, a fairness pipeline, or a chat interface as
the primary analyst surface. If a task seems to need one of these, stop and
ask — it means either the task is out of V1 scope or the checklist item is
being misread.

## Phase gate protocol

Build order is **Phase 0 → 1 → 2 → 3 → 4 → 5 → 6**, fixed by the checklist's
own closing line. This is a hard gate, not a suggestion:

- Do not start a Phase-N task while any Phase-(N-1) exit checkbox lacks
  evidence in the repo. "It's probably fine" is not evidence.
- Within a phase, follow the checklist's own item order. Don't reorder items
  because a later one looks easier or more interesting right now.
- Phase 2 (Evidence Agent) carries its own explicit gate in the checklist:
  its branching-proof exit criteria (§2.4) must be fully checked, with a
  logged 10-run success rate, before any Phase 3 work begins. This is called
  out because it's the highest-risk component — treat that emphasis as real.
- Phase 4's Policy work is additionally gated by Contracts §19 (`PolicyRule`
  shape) and §20 (Mandatory Policy Rules) being implemented exactly as
  frozen — six rules, `P-001`–`P-006`, `AUTO_RESOLVE`/`ESCALATE` only. Read
  those sections before touching `PolicyRule` or the evaluator; do not
  implement only five rules from memory of an earlier version.

If asked "what's next" or "are we done with Phase X," don't answer from
memory of a prior conversation — re-read the relevant checklist page and
check the repo for the evidence each item requires (below).

## What counts as evidence

A checklist item is complete when there is something in the repo a second
person could inspect and reach the same conclusion — not when the assistant
asserts it's done.

| Claim | Acceptable evidence |
|---|---|
| "Detection model evaluated" | `eval/detection_baseline.json` with precision/recall/ROC-AUC/PR-AUC/FN-rate actually populated from a held-out run |
| "Anomaly tag works" | A unit test file with at least one true and one false case, passing |
| "Branching behavior proven" | A logged tool-call sequence across ≥10 runs, saved somewhere in the repo (not just a claim in a chat message) |
| "Citation validation works" | A test asserting a fabricated `fact_id` is rejected |
| "Policy rule correct" | A unit test at the exact threshold boundary, passing |
| "Pipeline runs end-to-end" | An actual run of the seeded scenarios from Phase 1.4 through the full pipeline, with observed output matching expectation |
| "Ready to submit" | Every Phase 6.5 final-gate line individually checked against real artifacts, not assumed from earlier phases going well |

If the only evidence offered is "I ran it and it looked right," that is not
evidence — get the artifact into the repo (a JSON file, a test, a saved log)
or don't check the box.

## Review mode: no code changes

When the task is to review progress, review a diff, or check checklist
status against the PDF, **make no edits to application code**
(`services/`, `shared/`, `ui/`, `scripts/`, `tests/`, `data/`, `models/`,
`eval/`). Report findings — what's checked, what's missing evidence, what
violates an invariant — and stop there. Fixing what the review finds is a
separate, explicitly requested task.

## Secrets, datasets, binaries, and generated artifacts

Never stage or commit: `.env` files, raw datasets (`data/raw/*`,
`data/processed/*` beyond the allowlisted metadata files), model binaries
(`*.joblib`, `*.pkl`), or other generated artifacts not already allowlisted
in `.gitignore`. Before any commit:

- Run `git status` and read every new/modified path, not just the ones you
  expect.
- If `git add` was broad, run `git status` again post-stage and look for
  anything that shouldn't be there — a suspiciously named file is worth
  opening before it's pushed.
- `.gitignore` already encodes most of this; treat a file that *should* be
  ignored but isn't caught as a `.gitignore` gap to fix, not a one-off `git
  rm` to forget about next time.

## Completion requires tests, verification, and a clean diff

Before reporting any task complete: run the relevant test suite
(`python -m pytest`), confirm it passes, and review the actual staged diff
— not a summary of what you meant to change. **REQUIRED SUB-SKILL:** use
superpowers:verification-before-completion before claiming anything is
fixed, passing, or done. Evidence before assertions, every time.

## Rationalization table

| Excuse | Reality |
|---|---|
| "This is basically Phase 2, close enough to start it" | Phase 1 exit evidence doesn't exist until it's in the repo. Close enough isn't the gate. |
| "The branching scenario worked once, it's fine" | The checklist requires ≥10 repeated runs with a logged success rate specifically because "worked once" is not reliability. |
| "I'll add the eval numbers file after the real work" | The eval file *is* the evidence the real work happened. Without it there is nothing to check off. |
| "It's just a small integration, not really architecture drift" | Any dependency/service/store not named in the Architecture doc or the checklist is drift by definition, regardless of size. |
| "The judge/user wants speed, this rule can flex this once" | The safety invariants and phase gate exist because of deadline pressure, not despite it — that's exactly when they matter most. |
| "I already reviewed it, might as well fix the small stuff I found" | Review mode is read-only. A finding gets fixed in a separate, requested pass. |
| "It's just a fixture/log file, doesn't count as a generated artifact" | If it's derived rather than authored, and not already allowlisted in `.gitignore`, treat it as an artifact until proven otherwise. |
| "Gemini's recommendation is basically the decision, Policy just rubber-stamps it" | Policy is the sole automated disposition authority and can only ever emit `AUTO_RESOLVE`/`ESCALATE`. Reasoning output is advisory input, never the decision. |

## Red flags — stop and re-check the checklist

- About to start work on a phase whose predecessor has any unchecked or
  unevidenced exit item.
- About to mark something complete based on a description of a run rather
  than a saved artifact.
- About to add a library, service, queue, or datastore not named in the
  Architecture doc or checklist.
- About to write code while the task was framed as a review.
- About to stage a commit without having actually read `git status` /
  `git diff` output.
- Any code path that could plausibly reach `BLOCK_HOLD` or `AUTO_DECLINE`
  outside the human-decision endpoint.

**All of these mean: stop, re-read the checklist page and/or the frozen
contracts section, and proceed only once the gate is actually satisfied.**
