We are modifying the existing Sentinel V1 application.

This is a focused judge-facing UX/demo enhancement of the existing
Transaction Investigation Console.

DO NOT start coding immediately.

FIRST inspect the existing implementation and frozen contracts.
Then implement only what is requested below.

============================================================
0. NON-NEGOTIABLE ARCHITECTURE RULE
============================================================

Sentinel V1 architecture remains:

Transaction
→ Detection
→ Evidence Agent
→ AI Reasoning
→ Robustness
→ Deterministic Policy
→ AUTO_RESOLVE or HUMAN_REVIEW
→ Analyst workflow / Audit

Safety invariant:

Probabilistic AI investigates and reasons.
Deterministic policy controls automated disposition.
Humans retain authority over blocking and overrides.

DO NOT modify:

- frozen Transaction contract
- CaseFindings contract
- Evidence Agent contracts
- AI reasoning contracts
- robustness implementation
- deterministic policy rules
- HumanDecisionRequest
- human decision semantics
- case authorization
- Firebase role semantics
- Firestore security model
- protected GET /cases APIs
- existing round-robin semantics
- existing audit semantics

Gemini/AI must NEVER directly approve, decline, block, release,
or move money.

The new upload feature is ONLY an input adapter that converts
uploaded transaction documents into the EXISTING frozen transaction
request schema.

Do not create a competing transaction model.

============================================================
1. CURRENT PROBLEM
============================================================

The current /investigate UI looks like an internal developer form.

It currently contains:

- Clean Transaction button
- Suspicious / Flagship Transaction button
- large manual transaction form
- Case queue button
- Sign out button
- static pipeline dots

This is NOT the desired judge-facing experience.

The page must become a polished transaction investigation console.

============================================================
2. PUBLIC ROUTING MUST REMAIN CORRECT
============================================================

/investigate MUST remain completely public.

It must NOT require Firebase authentication.

Keep:

/login                  PUBLIC
/investigate            PUBLIC

/                       PROTECTED
/case/:caseId           PROTECTED

Do NOT put /investigate inside RequireAuth again.

Do NOT weaken protection on / or /case/:caseId.

Do NOT weaken backend authorization.

============================================================
3. REMOVE THESE ELEMENTS FROM /investigate
============================================================

Remove from the public investigation console:

- Sign out
- Case queue
- Clean Transaction button
- Suspicious / Flagship Transaction button
- the large manual transaction form
- demo scenario selection buttons/cards

There must NOT be UI such as:

[Single Clean]
[Single Fraud]
[25 Transaction Batch]
[Choose Demo File]

There must be NO built-in demo transaction selector.

The judge should see a real upload workflow.

I will manually select the appropriate PDF from my computer.

============================================================
4. NEW PUBLIC INVESTIGATION EXPERIENCE
============================================================

The primary workflow must be:

UPLOAD
   ↓
EXTRACT
   ↓
VALIDATE
   ↓
PREVIEW
   ↓
RUN INVESTIGATION
   ↓
LIVE VISUAL PIPELINE
   ↓
FINAL ROUTING / BATCH SUMMARY

The page should immediately communicate:

"Upload transaction records and Sentinel will investigate them."

============================================================
5. THREE EXTERNAL DEMO PDF FILES
============================================================

I will maintain three PDFs OUTSIDE the application.

They are NOT buttons or built-in scenarios.

PDF 1:
sentinel_clean_transaction.pdf

Contains:
1 clean/normal transaction.

PDF 2:
sentinel_fraud_transaction.pdf

Contains:
1 suspicious/fraud-pattern transaction.

PDF 3:
sentinel_batch_25_transactions.pdf

Contains:
25 transactions total:

10 clean/normal transaction inputs
15 suspicious/fraud-pattern transaction inputs

These files are manually uploaded through the same upload interface.

The UI must NOT know or care which demo file I selected.

It must simply parse whatever valid supported transaction document
the user uploads.

Do not hardcode these filenames into product behavior.

============================================================
6. UPLOAD UI
============================================================

Replace the existing transaction form with a polished drag-and-drop
upload zone.

Conceptually:

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                       Upload transactions                    │
│                                                              │
│              Drop your transaction file here                 │
│                       or browse                              │
│                                                              │
│                      PDF • DOCX                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘

This is conceptual only.
Use the existing Sentinel visual language and design system.

The entire drop area should be clickable.

Support:

- PDF
- DOCX

If supporting legacy .doc safely requires a separate dependency or
unreliable parser, do NOT silently add it.

Report that limitation instead.

Show upload state cleanly:

Uploading
→ Extracting
→ Validating
→ Ready

Do not automatically run transactions immediately after file upload.

The user should review what was extracted first.

============================================================
7. DOCUMENT PARSING
============================================================

Implement a real document input adapter.

It must:

1. accept PDF/DOCX
2. extract transaction records
3. map extracted fields into the EXISTING frozen transaction schema
4. validate every transaction
5. reject malformed records clearly
6. never silently invent required transaction fields

Do not create a new domain transaction contract.

The final parsed objects must be valid inputs for the existing:

POST /transactions

endpoint.

IMPORTANT:

Do NOT use an LLM to invent missing financial transaction fields.

For the controlled demo PDFs, deterministic parsing is preferred.

If parsing fails, display a useful error.

============================================================
8. SINGLE TRANSACTION EXPERIENCE
============================================================

If the uploaded document contains exactly one transaction:

Show a compact preview.

Example:

TRANSACTION READY

$499.99 USD

Electronics
WEB • PRE_AUTH
Miami, USA

Transaction ID
tx_xxxxx

Customer
cust_xxxxx

Device
dev_xxxxx

[ Investigate Transaction ]

Do NOT display the old giant form.

Provide an expandable:

View transaction details

section if all raw fields need to be inspected.

============================================================
9. BATCH EXPERIENCE
============================================================

If the document contains multiple transactions:

Show:

TRANSACTION BATCH

25 transactions detected

Then display a clean preview table.

Example:

Transaction       Amount       Merchant       Channel       Status

TX-001             $42.50      Grocery        WEB           Ready
TX-002            $899.00      Electronics    WEB           Ready
TX-003             $75.20      Retail         MOBILE        Ready
...

The user should click ONE button:

[ Run Investigation ]

Do NOT require 25 manual clicks.

============================================================
10. IMPORTANT DEMO LABEL RULE
============================================================

The 25-transaction PDF contains:

10 clean/normal INPUT examples
15 suspicious/fraud-pattern INPUT examples.

These labels are DEMO DATASET COMPOSITION.

They are NOT Sentinel's final decisions.

Do NOT make the UI say:

"15 fraud detected"

before Sentinel actually investigates them.

Do NOT assume:

clean input = AUTO_RESOLVED
suspicious input = HUMAN_REVIEW

The real Sentinel pipeline determines actual routing.

This distinction is critical.

============================================================
11. REAL BATCH EXECUTION
============================================================

When Run Investigation is clicked:

Each parsed transaction must actually go through the existing:

POST /transactions

endpoint.

Do NOT bypass the orchestrator.

Do NOT generate frontend-only outcomes.

Do NOT fake policy results.

Do NOT fabricate analyst assignment.

Every transaction must have a unique transaction_id.

Handle duplicate transaction IDs using the existing idempotency
behavior.

============================================================
12. BATCH EXECUTION SAFETY
============================================================

Do not blindly fire 25 simultaneous requests if that could overload
the current V1 backend, Gemini calls, Vertex quotas, or agent limits.

Inspect the current backend first.

Implement controlled concurrency appropriate for the existing V1
architecture.

For example, use a small bounded worker pool if appropriate.

The exact concurrency level must be justified from the current
implementation.

Do NOT modify the investigation semantics merely to make the demo
appear faster.

Display genuine progress:

3 / 25 completed
8 / 25 completed
17 / 25 completed
25 / 25 completed

based on actual completed transaction requests.

============================================================
13. REDESIGN THE PIPELINE JOURNEY
============================================================

The existing static dots:

Transaction received
Detection
Evidence Agent
AI Reasoning
Robustness
Policy

are visually weak.

Replace them with a premium visual investigation journey.

Required conceptual stages:

TRANSACTION
      ↓
DETECTION
      ↓
EVIDENCE AGENT
      ↓
AI REASONING
      ↓
ROBUSTNESS
      ↓
POLICY
      ↓
ROUTING

Each node should have visual states such as:

WAITING
ACTIVE
COMPLETE
ERROR

Use restrained enterprise-quality motion:

- animated connector
- progress movement
- active stage emphasis
- checkmarks
- subtle pulse/glow
- smooth state transitions
- clear stage labels

Do NOT create a gaming/neon interface.

This is BFSI enterprise software.

============================================================
14. ABSOLUTELY NO FAKE PIPELINE TELEMETRY
============================================================

Before implementing stage-by-stage animation, inspect what the
backend ACTUALLY exposes during POST /transactions.

If the backend currently exposes only:

request started
→ final POST response

then the frontend does NOT have evidence that:

Detection finished at second 1
Evidence Agent finished at second 2
AI Reasoning finished at second 3
etc.

Therefore:

DO NOT fabricate backend stage completion events.

DO NOT fabricate:

- evidence count
- tools called
- AI findings
- stage durations
- reasoning results
- robustness results
- policy results

just for animation.

You may create a clearly presentational "investigation in progress"
animation while the real request is executing.

But it must not falsely represent fabricated backend telemetry.

If genuine stage events already exist, use them.

If they do not exist, do NOT redesign backend contracts just for
animation without stopping and reporting the gap first.

Final status MUST always be based on the actual POST response.

============================================================
15. SINGLE TRANSACTION VISUAL STORY
============================================================

For a one-transaction upload, the judge should experience:

Upload PDF

→ extracting transaction

→ transaction preview

→ Investigate Transaction

→ visually watch Sentinel investigation

→ final routing

For clean transaction, if the REAL backend returns AUTO_RESOLVED,
show a polished result such as:

AUTO RESOLVED

Rule: P-004

No analyst action required.

For suspicious transaction, if the REAL backend returns HUMAN_REVIEW:

HUMAN REVIEW

Rule: P-xxx

Case: case_xxxxx

Assigned to: <Normal Analyst Display Name>

[ Open Case ]

Do not hardcode the expected rule/outcome.

Use actual response values.

============================================================
16. OPEN CASE BEHAVIOR
============================================================

The public console MUST NOT call:

GET /cases/{case_id}

to retrieve protected case information.

The public console may show only the safe routing information returned
by POST /transactions.

If HUMAN_REVIEW returns a case_id:

show:

[ Open Case ]

If clicked while logged out:

→ /login

After successful authentication:

→ navigate to the requested protected case

Existing backend authorization still decides whether the authenticated
analyst may view that case.

Do NOT bypass assigned analyst authorization.

============================================================
17. PUBLIC ASSIGNMENT PRIVACY
============================================================

For HUMAN_REVIEW, the public console may show ONLY:

Assigned to: <Analyst Display Name>

Example:

Assigned to: Meera Nair

Never expose publicly:

- analyst email
- Firebase UID
- role
- internal directory ID
- senior analyst identity
- credentials

If assignment is null:

No analyst is currently available.

If an existing duplicate case is currently assigned to a
SENIOR_ANALYST:

the public response must remain assignment:null.

Do NOT expose the senior analyst.

============================================================
18. ANALYST DIRECTORY DEMO DATA
============================================================

We need a realistic analyst workforce for the demo.

Create exactly:

15 active ANALYST accounts

7 active SENIOR_ANALYST accounts

Roles remain EXACTLY:

ANALYST
SENIOR_ANALYST

No ADMIN role.

Use professional realistic human names.

DO NOT create names such as:

Analyst 1
Analyst 2
Senior Analyst 1
User 01

Use natural professional names.

Use a diverse set of realistic names suitable for an enterprise
financial investigation team.

============================================================
19. FIREBASE AUTH ACCOUNTS
============================================================

Every seeded analyst must have:

- unique Firebase Auth account
- unique email
- unique password
- corresponding analyst directory record
- correct Firebase UID mapping
- correct role
- active=true

15 users must be ANALYST.

7 users must be SENIOR_ANALYST.

============================================================
20. PASSWORD SECURITY
============================================================

Passwords must NOT be identical.

Each demo account must receive a different strong password.

Do NOT:

- hardcode passwords into frontend source
- commit passwords to Git
- place passwords in README
- expose passwords through an API
- store plaintext passwords in Firestore
- display passwords in /investigate

Use an appropriate admin/demo seed mechanism.

If a local credentials output file is necessary for the demo operator,
it MUST be gitignored.

Before creating credentials, inspect existing .gitignore and ensure
the credentials artifact cannot be committed.

Firebase Auth owns authentication credentials.

The analyst directory should store profile/role/active information,
not plaintext passwords.

============================================================
21. ROUND-ROBIN ALLOCATION
============================================================

Preserve the existing deterministic round-robin assignment system.

Normal HUMAN_REVIEW cases must be assigned ONLY to:

active ANALYST

Never to:

SENIOR_ANALYST

With 15 active analysts, the batch demonstration should naturally
show workload distribution according to the existing deterministic
allocation implementation.

Do NOT fake distribution in the UI.

Use actual backend assignments.

============================================================
22. SENIOR ANALYST BEHAVIOR
============================================================

Senior analysts are excluded from normal case allocation.

They only enter the workflow through the existing:

ESCALATE_SENIOR

action.

ESCALATE_SENIOR remains reassignment only.

Case remains:

HUMAN_REVIEW

It must not become FINALIZED merely because it was escalated.

Senior cannot escalate again.

Do not modify these semantics.

============================================================
23. BATCH VISUALIZATION
============================================================

For a multi-transaction investigation, design a live batch operations
view.

Conceptually:

SENTINEL INVESTIGATION

Processing transaction batch

████████████████░░░░░░

17 / 25 completed

AUTO RESOLVED       HUMAN REVIEW       PROCESSING       FAILED
      8                   7                 10              0

These numbers must be computed from REAL request states/responses.

Do not hardcode them.

============================================================
24. CURRENT TRANSACTION PANEL
============================================================

While processing the batch, show which transaction(s) are currently
being investigated.

Example:

CURRENTLY INVESTIGATING

TX-018
$980.00 USD
Electronics
WEB

Evidence investigation in progress...

Again:

Do not fabricate evidence findings.

============================================================
25. BATCH RESULTS
============================================================

When all actual requests complete, show:

INVESTIGATION COMPLETE

25 transactions processed

Then actual routing totals, for example:

AUTO RESOLVED       HUMAN REVIEW       FAILED
      X                   Y               Z

These values MUST be calculated from the real POST responses.

Do not hardcode 10/15 as final outcomes.

============================================================
26. ANALYST WORKLOAD VISUALIZATION
============================================================

For actual HUMAN_REVIEW responses that contain a normal analyst
assignment, aggregate them.

Show a polished section:

ANALYST WORKLOAD

Meera Nair          2 cases
Arjun Rao           1 case
Priya Shah          1 case
...

This must be calculated ONLY from actual assignment names returned by
the backend.

Do NOT fabricate assignments.

Do NOT expose emails or UIDs.

Do NOT include SENIOR_ANALYST users.

This is an important judge-facing demonstration:

Sentinel not only investigates transactions but routes human-review
work across the active analyst pool.

============================================================
27. BATCH TRANSACTION RESULTS
============================================================

Show each actual processed transaction.

Example:

TX-001       $42.50       AUTO RESOLVED
TX-002      $899.00       HUMAN REVIEW       Meera Nair
TX-003       $75.20       AUTO RESOLVED
...

Each row must come from the actual transaction request + actual
POST response.

If a transaction failed:

show FAILED clearly with an appropriate safe error state.

Do not silently count failed transactions as clean or suspicious.

============================================================
28. OPTIONAL DETAIL INTERACTION
============================================================

Allow selecting a processed transaction to show its public-safe
transaction/routing details.

Do NOT automatically call protected GET /cases/{case_id}.

For HUMAN_REVIEW transactions, provide Open Case separately.

============================================================
29. UI / UX QUALITY
============================================================

UI/UX is part of judging.

Treat this as a serious enterprise financial investigation product.

Design direction:

- professional dark BFSI interface
- clear visual hierarchy
- excellent spacing
- readable typography
- subtle borders
- strong status distinction
- polished cards
- restrained animation
- meaningful motion
- responsive layout
- accessible contrast
- clear loading/error states
- no horizontal clipping

Must look good at minimum:

1366x768
1920x1080

Avoid:

- giant forms
- unnecessary gradients
- excessive neon
- gaming aesthetics
- decorative animations
- clutter
- tiny text
- excessive technical JSON
- fake terminal interfaces
- excessive badges
- meaningless charts

The judge should understand the workflow without needing someone to
explain every control.

============================================================
30. PRODUCT HEADER
============================================================

The public console should have a simple product identity.

Example conceptual hierarchy:

SENTINEL

Transaction Investigation Console

Investigate suspicious transactions with evidence-driven AI and
deterministic policy controls.

Do not show:

Case Queue
Sign Out

on the public console.

A subtle:

Analyst Login

navigation option is acceptable if appropriate.

Do not make authentication the visual focus of this page.

============================================================
31. ERROR EXPERIENCE
============================================================

Create professional states for:

- unsupported file
- extraction failure
- malformed transaction
- duplicate transaction
- backend unavailable
- individual batch transaction failure
- complete batch failure
- no analyst available

Errors must not crash the entire batch unnecessarily.

If one transaction fails and the architecture safely permits
continuing, preserve the result and continue processing remaining
transactions.

Report failed count accurately.

============================================================
32. THREE DEMO FLOWS MUST WORK THROUGH SAME UI
============================================================

There are NO scenario buttons.

All three demonstrations use the exact same upload control.

FLOW A:

Manually upload:
sentinel_clean_transaction.pdf

Expected UX:

Upload
→ Extract 1
→ Preview
→ Investigate
→ Visual pipeline
→ Actual routing

FLOW B:

Manually upload:
sentinel_fraud_transaction.pdf

Expected UX:

Upload
→ Extract 1
→ Preview
→ Investigate
→ Visual pipeline
→ Actual routing
→ if HUMAN_REVIEW, display normal assigned analyst name
→ Open Case

FLOW C:

Manually upload:
sentinel_batch_25_transactions.pdf

Expected UX:

Upload
→ Extract 25
→ Preview
→ Run Investigation
→ Live batch processing
→ actual pipeline calls
→ actual routing results
→ actual analyst distribution
→ batch summary

The application itself must NOT display labels saying:

"Demo 1"
"Demo 2"
"Demo 3"

or buttons corresponding to these files.

============================================================
33. DEMO PDF COMPATIBILITY
============================================================

Before finalizing the parser, test it against the actual three
provided demo PDF structures.

Expected record counts:

sentinel_clean_transaction.pdf
→ exactly 1 transaction

sentinel_fraud_transaction.pdf
→ exactly 1 transaction

sentinel_batch_25_transactions.pdf
→ exactly 25 transactions

Batch composition in source document:

10 CLEAN input records
15 SUSPICIOUS input records

Again:

those source labels are not final Sentinel outcomes.

============================================================
34. DO NOT CLAIM "EFFICIENCY" WITHOUT MEASUREMENT
============================================================

The batch UI may display REAL measured values such as:

25 transactions processed
completed count
elapsed wall-clock time

if actually measured by the application.

Do not invent:

"95% faster"
"10x more efficient"
"real-time at enterprise scale"

without evidence.

For the judge demo, actual measured batch completion time is enough.

If appropriate, show:

Batch completed in 00:XX

using actual elapsed client-side wall-clock duration.

Label it clearly as the demo batch execution duration, not production
throughput benchmarking.

============================================================
35. AUDIT EXISTING IMPLEMENTATION BEFORE CODING
============================================================

Inspect at minimum:

Frontend:
- ui/src/App.tsx
- InvestigationConsolePage
- InvestigationResultPanel
- PipelineStrip/current pipeline component
- API wrapper
- Firebase auth context
- protected route behavior
- frontend tests

Backend:
- POST /transactions
- frozen Transaction request schema
- orchestrator
- assignment implementation
- analyst directory model/storage
- Firebase Admin integration
- role checks
- current seed tooling
- duplicate/idempotency behavior
- existing test fixtures

Also inspect:

- .gitignore
- environment configuration
- existing PDF/document parsing dependencies
- Docker/build implications

Report any architecture conflict BEFORE changing frozen behavior.

============================================================
36. TEST REQUIREMENTS
============================================================

Add/modify tests proving:

ROUTING

1. /investigate works logged out.
2. / redirects logged-out user to login.
3. /case/:caseId remains protected.
4. public console does not fetch protected case content.

UPLOAD

5. valid PDF accepted.
6. valid DOCX accepted if implemented.
7. invalid file rejected.
8. extraction errors displayed safely.

PARSING

9. clean PDF extracts exactly 1 transaction.
10. fraud PDF extracts exactly 1 transaction.
11. batch PDF extracts exactly 25 transactions.
12. batch contains 25 unique transaction IDs.
13. all extracted records validate against existing transaction schema.
14. no required transaction fields are invented silently.

BATCH

15. Run Investigation submits all 25 through existing POST /transactions.
16. controlled concurrency is used.
17. completed counter reflects actual completions.
18. failures are counted correctly.
19. final totals come from actual responses.
20. batch elapsed time is measured, not hardcoded.

ASSIGNMENT

21. active normal ANALYST receives HUMAN_REVIEW assignments.
22. SENIOR_ANALYST is excluded from normal allocation.
23. public assignment contains display name only.
24. public UI never displays analyst email.
25. public UI never displays Firebase UID.
26. public UI never displays senior assignment.
27. analyst workload summary is calculated from actual responses.

SEEDING

28. analyst directory contains exactly 15 active ANALYST users.
29. analyst directory contains exactly 7 active SENIOR_ANALYST users.
30. all 22 Firebase accounts are unique.
31. all emails are unique.
32. all generated passwords are unique.
33. passwords are not stored in Firestore.
34. credentials are not committed.
35. credentials output is gitignored.

REGRESSION

36. existing backend tests continue to pass.
37. existing frontend tests continue to pass.
38. TypeScript typecheck passes.
39. production frontend build passes.
40. backend startup/build remains valid.

============================================================
37. LIVE DEMO VERIFICATION
============================================================

After automated tests, perform live verification where tooling permits.

Do NOT claim a real browser test if no browser automation/tool is
available.

For actual backend tests, verify:

A. single clean PDF:
   extracted count = 1
   actual POST /transactions executed
   record actual response

B. single fraud PDF:
   extracted count = 1
   actual POST /transactions executed
   record actual response
   if HUMAN_REVIEW, verify normal analyst assignment

C. batch PDF:
   extracted count = 25
   25 unique transaction requests
   record completed count
   record failed count
   record actual AUTO_RESOLVED count
   record actual HUMAN_REVIEW count
   record actual analyst assignment distribution
   record measured execution time

Do not predict these numbers before execution.

============================================================
38. IMPORTANT COST / PERSISTENCE WARNING
============================================================

The batch test may cause:

- real Gemini/Vertex calls
- Firestore writes
- case creation
- analyst assignments
- audit entries

Before running the full 25-transaction LIVE batch against production
or shared persistent data:

STOP and tell me exactly what persistent/cost-bearing effects will
occur.

Do NOT create 25 production/shared cases merely for verification
without telling me first.

Automated mocked/integration tests may be run normally where they do
not create external persistent resources.

============================================================
39. CREDENTIAL CREATION WARNING
============================================================

Creating 22 Firebase Authentication users is an external persistent
change.

Before actually creating those 22 accounts:

STOP and report:

- which Firebase project will be modified
- how accounts will be created
- what analyst directory records will be created
- where generated credentials will be written locally
- confirmation that the credential file is gitignored

Then wait for my approval before executing the persistent seed.

Do not ask me to paste credentials into chat.

============================================================
40. COMPLETION REPORT
============================================================

Do NOT say "complete" merely because code was written.

At the end report exactly:

FILES CHANGED

BACKEND TESTS
x/x

FRONTEND TESTS
x/x

TYPECHECK
PASS/FAIL

LINT
PASS/FAIL + existing warnings if any

BUILD
PASS/FAIL

PDF EXTRACTION

Clean:
expected 1
actual X

Fraud:
expected 1
actual X

Batch:
expected 25
actual X

TRANSACTION VALIDATION
x/x valid

ANALYST SEED CODE
PASS/FAIL

PERSISTENT FIREBASE SEED
NOT RUN / RUN WITH USER APPROVAL

ROLE COUNTS
ANALYST = X
SENIOR_ANALYST = X

CREDENTIAL SAFETY
PASS/FAIL

PUBLIC ROUTE
PASS/FAIL

PROTECTED ROUTES
PASS/FAIL

LIVE SINGLE CLEAN
NOT RUN / actual result

LIVE SINGLE FRAUD
NOT RUN / actual result

LIVE 25 BATCH
NOT RUN / actual measured result

REAL BROWSER VERIFICATION
NOT PERFORMED / PASS / FAIL

KNOWN LIMITATIONS
...

============================================================
41. STOP CONDITIONS
============================================================

STOP instead of improvising if:

- frozen contracts would need modification
- POST /transactions cannot safely support the proposed adapter
- PDF parsing requires inventing transaction fields
- genuine pipeline stage telemetry is unavailable and implementing it
  would alter frozen architecture/contracts
- Firebase project/account target is ambiguous
- persistent 22-user Firebase seeding is about to happen without my
  approval
- live 25-transaction execution will create persistent/cost-bearing
  resources without my approval

Do not silently work around architecture constraints.

============================================================
42. FINAL GOAL
============================================================

The judge-facing story should be immediately understandable:

A transaction file arrives.

Sentinel extracts and validates the transactions.

For a single transaction:
Sentinel investigates it through the real pipeline and determines
routing.

For a batch:
Sentinel processes many transactions through the same real pipeline,
shows actual progress and actual routing, and distributes genuine
human-review cases across the normal analyst workforce.

Then an assigned analyst can authenticate separately, inspect their
protected case, review evidence, use counterfactual analysis, and make
the permitted human decision.

The UI should visually demonstrate:

Detect
→ Investigate
→ Explain
→ Stress-test
→ Decide
→ Route

without fake AI, fake telemetry, fake assignments, fake results,
or weakened security.

START with the architecture/code audit.
Then implement the non-persistent changes.
Before Firebase user creation or live persistent 25-transaction
execution, STOP for my approval.