/**
 * Manual verification (Robustness/Counterfactual UI step) against the real
 * local dev server + real backend + real Firestore + real Gemini. Signs in
 * as analyst1 (owns case_363a3f9bb31b, 6 real evidence facts).
 */
import { chromium } from "playwright";

const sizes = [
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "1366x768", width: 1366, height: 768 },
];

let failures = [];
function check(cond, label) {
  console.log(`${cond ? "PASS" : "FAIL"}: ${label}`);
  if (!cond) failures.push(label);
}

const browser = await chromium.launch();

for (const size of sizes) {
  const page = await browser.newPage({ viewport: { width: size.width, height: size.height } });

  // Sign in
  await page.goto("http://localhost:5173/login", { waitUntil: "networkidle" });
  await page.fill('input[type="email"]', "analyst1@sentinel.demo");
  await page.fill('input[type="password"]', "SentinelDemo!2026");
  await page.click('button[type="submit"]');
  await page.waitForSelector("text=Case queue", { timeout: 15000 });
  await page.waitForFunction(() => !document.body.innerText.includes("Loading queue..."), { timeout: 15000 });

  // A. Case opens normally
  await page.goto("http://localhost:5173/case/case_363a3f9bb31b", { waitUntil: "networkidle" });
  await page.waitForSelector("text=Advisory", { timeout: 10000 });
  await page.waitForTimeout(300);
  check(await page.getByText("Gemini's assessment").count() > 0, `[${size.name}] A. case opens, original findings panel visible`);

  // Capture the original findings text for later "unchanged" comparison.
  const originalFindingsText = await page.locator("text=Gemini's assessment").locator("..").locator("..").innerText();

  await page.screenshot({ path: `../eval/ui_verification/cf-A-initial-${size.name}.png`, fullPage: true });

  // No counterfactual initially.
  check(
    (await page.getByText("LIVE COUNTERFACTUAL SIMULATION").count()) === 0,
    `[${size.name}] no simulation shown before Run`,
  );
  check(
    (await page.locator("text=Excluded from this re-check").count()) === 0,
    `[${size.name}] no exhibit excluded before Run`,
  );

  // C. Select exhibit 1 and run.
  const select = page.getByLabel(/Remove a fact/);
  await select.selectOption({ index: 1 }); // Exhibit 1
  const selectedLabel = await select.locator("option:checked").innerText();
  console.log(`[${size.name}] selected: ${selectedLabel}`);

  const runClickPromise = page.getByRole("button", { name: "Run" }).click();
  // E. Loading state visible (best-effort: check quickly after click).
  await page.waitForTimeout(50);
  const loadingVisible = await page.getByRole("button", { name: "Re-running investigation..." }).count();
  check(loadingVisible > 0, `[${size.name}] E. 'Re-running investigation...' loading state appears`);
  await runClickPromise;

  await page.waitForSelector("text=LIVE COUNTERFACTUAL SIMULATION", { timeout: 40000 });
  await page.waitForTimeout(300);

  // F/G/H/I/J
  check(await page.getByText("LIVE COUNTERFACTUAL SIMULATION").count() > 0, `[${size.name}] F. real counterfactual result appears`);
  check(await page.getByText("Risk assessment:").count() > 0, `[${size.name}] G. risk assessment appears`);
  check(await page.getByText("AI advisory disposition:").count() > 0, `[${size.name}] H. AI advisory disposition appears`);
  check(await page.getByText("Robustness:").count() > 0, `[${size.name}] I. robustness appears`);
  check(
    (await page.getByText(/policy outcome would (not )?change/).count()) > 0,
    `[${size.name}] J. policy outcome change appears`,
  );

  // D. Exhibit 1 shows Excluded from this re-check.
  const excludedCount = await page.locator("text=Excluded from this re-check").count();
  check(excludedCount === 1, `[${size.name}] D. exactly one exhibit shows 'Excluded from this re-check'`);

  await page.screenshot({ path: `../eval/ui_verification/cf-D-excluded-${size.name}.png`, fullPage: true });

  // K/L: supporting/counter factors + citations (best-effort presence check).
  const hasSupporting = (await page.getByText("Remaining supporting factors").count()) > 0;
  const hasCounter = (await page.getByText("Remaining counter factors").count()) > 0;
  const hasCitations = (await page.getByText("Remaining citations").count()) > 0;
  console.log(`[${size.name}] K/L supporting=${hasSupporting} counter=${hasCounter} citations=${hasCitations}`);
  check(hasSupporting || hasCounter || hasCitations, `[${size.name}] K/L at least one factor/citation section rendered`);

  // M/N: select a different exhibit and run again.
  await select.selectOption({ index: 3 }); // Exhibit 3
  const secondLabel = await select.locator("option:checked").innerText();
  console.log(`[${size.name}] second selection: ${secondLabel}`);
  await page.getByRole("button", { name: "Run" }).click();
  await page.waitForFunction(
    () => !document.body.innerText.includes("Re-running investigation..."),
    { timeout: 40000 },
  );
  await page.waitForTimeout(300);

  const excludedAfterSecond = await page.locator("text=Excluded from this re-check").count();
  check(excludedAfterSecond === 1, `[${size.name}] N. exactly one exhibit excluded after second run (moved, not duplicated)`);

  await page.screenshot({ path: `../eval/ui_verification/cf-N-second-run-${size.name}.png`, fullPage: true });

  // O. Original persisted findings text unchanged.
  const findingsTextAfter = await page.locator("text=Gemini's assessment").locator("..").locator("..").innerText();
  check(findingsTextAfter === originalFindingsText, `[${size.name}] O. original findings panel text unchanged after simulations`);

  await page.close();
}

await browser.close();

console.log("\n=== SUMMARY ===");
console.log(failures.length === 0 ? "ALL CHECKS PASSED" : "FAILURES:\n" + failures.join("\n"));
