/**
 * Build Checklist Phase 5.4: "Test the UI on the actual screen size/
 * resolution you'll demo on." Runs the real dev server against the real
 * running backend/Firestore data, captures real screenshots at common
 * demo resolutions, and flags horizontal overflow. Requires both
 * `npm run dev` (this directory) and the backend (services/api/main.py)
 * already running. Output: ../eval/ui_verification/*.png.
 */
import { chromium } from "playwright";

const sizes = [
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "1366x768", width: 1366, height: 768 },
];

const browser = await chromium.launch();

for (const size of sizes) {
  const page = await browser.newPage({ viewport: { width: size.width, height: size.height } });

  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `../eval/ui_verification/queue-${size.name}.png` });

  const overflowQueue = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log(`${size.name} queue horizontal overflow: ${overflowQueue}`);

  const rows = await page.locator("table tbody tr").all();
  if (rows.length > 0) {
    await rows[0].locator("a").first().click();
    await page.waitForSelector("text=Advisory", { timeout: 8000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: `../eval/ui_verification/detail-${size.name}.png`, fullPage: true });

    const overflowDetail = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    console.log(`${size.name} detail horizontal overflow: ${overflowDetail}`);
  }

  await page.close();
}

await browser.close();
