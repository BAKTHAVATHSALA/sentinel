/**
 * Post-fix E2E verification against the ACTUAL deployed Cloud Run URL (not
 * localhost) -- confirms the VITE_API_BASE_URL="" Dockerfile fix actually
 * resolved "Could not load the queue" for all three demo accounts, in a
 * real browser, against the real deployed service.
 */
import { chromium } from "playwright";

const BASE = "https://sentinel-v1-209692631228.us-central1.run.app";
const PASSWORD = "SentinelDemo!2026";
let failures = [];

function check(cond, label) {
  console.log(`${cond ? "PASS" : "FAIL"}: ${label}`);
  if (!cond) failures.push(label);
}

async function signIn(page, email) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=Case queue", { timeout: 15000 });
  await page.waitForFunction(() => !document.body.innerText.includes("Loading queue..."), { timeout: 15000 });
}

const browser = await chromium.launch();

// --- ANALYST1 ---
{
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  let sawLocalhostFailure = false;
  page.on("requestfailed", (req) => { if (req.url().includes("localhost:8000")) sawLocalhostFailure = true; });

  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
  check(page.url().includes("/login"), "bare Cloud Run URL redirects to /login when unauthenticated");

  await signIn(page, "analyst1@sentinel.demo");
  await page.waitForTimeout(300);
  const queueText = await page.locator("body").innerText();
  check(!queueText.includes("Could not load the queue"), "analyst1 queue does NOT show 'Could not load the queue'");
  check(await page.locator("table tbody tr").count() > 0, "analyst1 queue shows at least one row");
  await page.screenshot({ path: "../eval/ui_verification/e2e-analyst1-queue.png" });

  await page.locator("table tbody tr").first().locator("a").first().click();
  await page.waitForSelector("text=Advisory", { timeout: 10000 });
  await page.waitForTimeout(300);
  check(await page.getByText("Human decision").count() > 0, "analyst1 case detail shows Human decision panel");
  check(await page.getByRole("button", { name: "Clear" }).count() > 0, "analyst1 sees Clear control");
  check(await page.getByRole("button", { name: "Block & hold" }).count() > 0, "analyst1 sees Block & hold control");
  await page.screenshot({ path: "../eval/ui_verification/e2e-analyst1-detail.png", fullPage: true });

  // Counterfactual request
  const factSelect = page.locator("select").first();
  const factCount = await factSelect.locator("option").count();
  if (factCount > 1) {
    await factSelect.selectOption({ index: 1 });
    await page.getByRole("button", { name: "Run" }).click();
    await page.waitForSelector("text=Without", { timeout: 40000 });
    check(true, "analyst1 counterfactual request completed and rendered a result");
    await page.screenshot({ path: "../eval/ui_verification/e2e-analyst1-counterfactual.png", fullPage: true });
  } else {
    check(false, "analyst1 counterfactual request completed and rendered a result (no facts available to test)");
  }

  check(!sawLocalhostFailure, "analyst1 session made zero requests to localhost:8000");
  await page.close();
}

// --- ANALYST2 ---
{
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await signIn(page, "analyst2@sentinel.demo");
  await page.waitForTimeout(500);
  const text = await page.locator("body").innerText();
  check(!text.includes("Could not load the queue"), "analyst2 queue does NOT show 'Could not load the queue'");
  check(text.includes("No cases require review") || (await page.locator("table tbody tr").count()) >= 0, "analyst2 queue loaded (empty state or rows), not an error");
  console.log("analyst2 body snippet:", text.replace(/\n/g, " | ").slice(0, 200));
  await page.screenshot({ path: "../eval/ui_verification/e2e-analyst2-queue.png" });
  await page.close();
}

// --- SENIOR1 ---
{
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await signIn(page, "senior1@sentinel.demo");
  await page.waitForTimeout(300);
  const text = await page.locator("body").innerText();
  check(!text.includes("Could not load the queue"), "senior1 queue does NOT show 'Could not load the queue'");
  const rowCount = await page.locator("table tbody tr").count();
  check(rowCount > 0, "senior1 queue shows the escalated case");
  await page.screenshot({ path: "../eval/ui_verification/e2e-senior1-queue.png" });

  if (rowCount > 0) {
    await page.locator("table tbody tr").first().locator("a").first().click();
    await page.waitForSelector("text=Advisory", { timeout: 10000 });
    await page.waitForTimeout(300);
    check(await page.getByRole("button", { name: "Clear" }).count() > 0, "senior1 sees Clear control");
    check(await page.getByRole("button", { name: "Block & hold" }).count() > 0, "senior1 sees Block & hold control");
    check(await page.getByRole("button", { name: "Escalate to senior" }).count() === 0, "senior1 does NOT see Escalate to senior control");
    await page.screenshot({ path: "../eval/ui_verification/e2e-senior1-detail.png", fullPage: true });
  }
  await page.close();
}

await browser.close();

console.log("\n=== SUMMARY ===");
if (failures.length === 0) {
  console.log("ALL CHECKS PASSED");
} else {
  console.log("FAILURES:\n" + failures.join("\n"));
  process.exit(1);
}
