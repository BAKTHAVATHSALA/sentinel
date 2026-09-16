/**
 * Post-Phase-B-J visual verification: login, queue, case detail, escalate
 * dropdown, senior view, counterfactual UI -- against the real running dev
 * server (npm run dev, port 5173) and real running backend (uvicorn, port
 * 8000), real Firestore data, real Firebase Auth.
 *
 * Current real state assumed: case_363a3f9bb31b assigned to analyst1 (used
 * for detail/escalate-dropdown-preview/counterfactual, not submitted);
 * case_e41fc15a8461 already escalated to senior1 (used for the senior view).
 *
 * Raw-UID-leak check: greps the full rendered page text for every real
 * analyst UID and fails loudly if any appear as visible text.
 */
import { chromium } from "playwright";

const RAW_UIDS = [
  "Kf7TBulMUnX9xOQYs6hNK9IBmTO2", // analyst1
  "EhgFAdXOTCPCV51bJ1j5ZavGGRc2", // analyst2
  "kyDqtXKjN3S9DChS3Qy7qEGE5Lz2", // senior1
];

let failures = [];

function checkNoRawUidLeak(pageText, label) {
  for (const uid of RAW_UIDS) {
    if (pageText.includes(uid)) {
      const msg = `FAIL raw UID leaked on ${label}: ${uid}`;
      console.log(msg);
      failures.push(msg);
    }
  }
}

function checkOverflow(overflow, label) {
  console.log(`${label} horizontal overflow: ${overflow}`);
  if (overflow) failures.push(`FAIL horizontal overflow on ${label}`);
}

async function signIn(page, email) {
  await page.goto("http://localhost:5173/login", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "SentinelDemo!2026");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=Case queue", { timeout: 10000 });
  // Give the queue fetch time to resolve and render before proceeding.
  await page.waitForFunction(() => !document.body.innerText.includes("Loading queue..."), { timeout: 15000 });
}

async function signOut(page) {
  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  const btn = page.getByRole("button", { name: "Sign out" });
  if (await btn.count()) {
    await btn.click();
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });
  }
}

const sizes = [
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "1366x768", width: 1366, height: 768 },
];

const browser = await chromium.launch();

for (const size of sizes) {
  const page = await browser.newPage({ viewport: { width: size.width, height: size.height } });
  page.setDefaultTimeout(15000);

  // 1. Login page
  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  await page.waitForSelector('input[type="email"]', { timeout: 10000 });
  await page.screenshot({ path: `../eval/ui_verification/auth-login-${size.name}.png` });
  checkOverflow(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), `${size.name} login`);
  checkNoRawUidLeak(await page.locator("body").innerText(), `login-${size.name}`);

  // 2. Sign in as analyst1 -- queue page (1 open case expected)
  await signIn(page, "analyst1@sentinel.demo");
  await page.waitForTimeout(300);
  await page.screenshot({ path: `../eval/ui_verification/auth-queue-analyst-${size.name}.png` });
  checkOverflow(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), `${size.name} analyst queue`);
  const analystRowCount = await page.locator("table tbody tr").count();
  console.log(`${size.name} analyst queue row count: ${analystRowCount}`);
  checkNoRawUidLeak(await page.locator("body").innerText(), `queue-analyst-${size.name}`);

  // 3. Case detail (case_363a3f9bb31b) -- escalate dropdown preview (not submitted) + counterfactual
  await page.goto("http://localhost:5173/case/case_363a3f9bb31b", { waitUntil: "networkidle" });
  await page.waitForSelector("text=Advisory", { timeout: 10000 });
  await page.waitForTimeout(300);
  await page.screenshot({ path: `../eval/ui_verification/auth-detail-analyst-${size.name}.png`, fullPage: true });
  checkOverflow(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), `${size.name} case detail`);
  checkNoRawUidLeak(await page.locator("body").innerText(), `detail-analyst-${size.name}`);

  await page.getByText("I have reviewed the evidence above").click();
  const escalateBtn = page.getByRole("button", { name: "Escalate to senior" });
  if (await escalateBtn.count()) {
    await escalateBtn.click();
    await page.waitForSelector("text=Escalate to");
    await page.screenshot({ path: `../eval/ui_verification/auth-escalate-dropdown-${size.name}.png` });
    const dropdownText = await page.locator("select").last().locator("option").allTextContents();
    console.log(`${size.name} escalate dropdown options: ${JSON.stringify(dropdownText)}`);
    checkNoRawUidLeak(await page.locator("body").innerText(), `escalate-dropdown-${size.name}`);
    await page.getByRole("button", { name: "Cancel" }).click();
  } else {
    failures.push(`FAIL no Escalate to senior control found for analyst on case_363a3f9bb31b at ${size.name}`);
  }

  const factSelect = page.locator("select").first();
  const factOptionCount = await factSelect.locator("option").count();
  if (factOptionCount > 1) {
    await factSelect.selectOption({ index: 1 });
    await page.getByRole("button", { name: "Run" }).click();
    await page.waitForSelector("text=/Robust|Fragile/", { timeout: 30000 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `../eval/ui_verification/auth-counterfactual-${size.name}.png`, fullPage: true });
    checkNoRawUidLeak(await page.locator("body").innerText(), `counterfactual-${size.name}`);
  } else {
    console.log(`${size.name}: no evidence facts available for counterfactual demo`);
  }

  // 4. Senior view: case_e41fc15a8461 was already escalated to senior1 for real earlier.
  await signOut(page);
  await signIn(page, "senior1@sentinel.demo");
  await page.waitForTimeout(300);
  await page.screenshot({ path: `../eval/ui_verification/auth-queue-senior-${size.name}.png` });
  checkOverflow(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), `${size.name} senior queue`);
  const seniorRowCount = await page.locator("table tbody tr").count();
  console.log(`${size.name} senior queue row count: ${seniorRowCount}`);
  checkNoRawUidLeak(await page.locator("body").innerText(), `queue-senior-${size.name}`);

  if (seniorRowCount > 0) {
    await page.locator("table tbody tr").first().locator("a").first().click();
    await page.waitForSelector("text=Advisory", { timeout: 10000 });
    await page.waitForTimeout(300);
    await page.screenshot({ path: `../eval/ui_verification/auth-detail-senior-${size.name}.png`, fullPage: true });
    checkOverflow(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), `${size.name} senior detail`);
    const hasEscalateButton = await page.getByRole("button", { name: "Escalate to senior" }).count();
    console.log(`${size.name} senior view has escalate control (should be 0): ${hasEscalateButton}`);
    if (hasEscalateButton !== 0) failures.push(`FAIL senior sees escalate control at ${size.name}`);
    checkNoRawUidLeak(await page.locator("body").innerText(), `detail-senior-${size.name}`);
  } else {
    failures.push(`FAIL senior queue is empty at ${size.name}, expected case_e41fc15a8461`);
  }

  await page.close();
}

await browser.close();
console.log("\n=== SUMMARY ===");
console.log(failures.length === 0 ? "No failures detected." : failures.join("\n"));
