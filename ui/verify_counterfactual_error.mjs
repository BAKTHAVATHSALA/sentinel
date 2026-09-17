import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

await page.goto("http://localhost:5173/login", { waitUntil: "networkidle" });
await page.fill('input[type="email"]', "analyst1@sentinel.demo");
await page.fill('input[type="password"]', "SentinelDemo!2026");
await page.click('button[type="submit"]');
await page.waitForSelector("text=Case queue", { timeout: 15000 });

await page.goto("http://localhost:5173/case/case_363a3f9bb31b", { waitUntil: "networkidle" });
await page.waitForSelector("text=Advisory", { timeout: 10000 });

// Force the simulate_without call specifically to fail with a real 500,
// while leaving every other request (including the plain case fetch)
// untouched -- a genuine, realistic backend-failure class.
await page.route("**/cases/case_363a3f9bb31b?simulate_without=*", (route) =>
  route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Internal Server Error" }) }),
);

const select = page.getByLabel(/Remove a fact/);
await select.selectOption({ index: 1 });
await page.getByRole("button", { name: "Run" }).click();
await page.waitForSelector("text=Try again", { timeout: 15000 });

const errorVisible = await page.getByRole("button", { name: "Try again" }).count();
const bodyText = await page.locator("body").innerText();
const hasStackTrace = /Traceback|at Object\.|at async|\.tsx:\d+/.test(bodyText);
const hasRawJson = bodyText.includes('{"detail"');

console.log("Try again button present:", errorVisible > 0);
console.log("No raw stack trace shown:", !hasStackTrace);
console.log("No raw JSON error body shown:", !hasRawJson);
console.log("Error message text:", bodyText.match(/Could not run the live re-check\.[^|]*/)?.[0] ?? "(not found verbatim)");

await page.screenshot({ path: "../eval/ui_verification/cf-P-error-1920x1080.png", fullPage: true });

// Clear the route override and retry for real -- confirm recovery works.
await page.unroute("**/cases/case_363a3f9bb31b?simulate_without=*");
await page.getByRole("button", { name: "Try again" }).click();
await page.waitForSelector("text=LIVE COUNTERFACTUAL SIMULATION", { timeout: 40000 });
console.log("Recovered after Try again:", (await page.getByText("LIVE COUNTERFACTUAL SIMULATION").count()) > 0);

await browser.close();
