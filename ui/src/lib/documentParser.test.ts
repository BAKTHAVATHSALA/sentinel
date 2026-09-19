import { describe, expect, it, vi } from "vitest";
import { extractRecordCandidates, parseTransactionDocument, UnsupportedFileTypeError, type RecordCandidate } from "./documentParser";

function fields(overrides: Record<string, string> = {}, omit: string[] = []): Record<string, string> {
  const base: Record<string, string> = {
    transaction_id: "tx_demo_001",
    customer_id: "cust_demo_001",
    account_id: "acc_2824",
    card_id: "card_1409",
    merchant_id: "merch_demo_electronics",
    amount: "499.99",
    currency: "USD",
    timestamp: "2026-09-13T14:00:00Z",
    authorization_stage: "PRE_AUTH",
    device_id: "dev_demo_99",
    ip_address: "198.51.100.88",
    geo_lat: "25.7617",
    geo_lon: "-80.1918",
    geo_country: "USA",
    channel: "WEB",
    merchant_category: "electronics",
    card_present: "false",
    ...overrides,
  };
  for (const key of omit) delete base[key];
  return base;
}

function candidate(recordLabel: string, overrides: Record<string, string> = {}, omit: string[] = []): RecordCandidate {
  return { recordLabel, fields: fields(overrides, omit) };
}

describe("parseTransactionDocument (validation)", () => {
  it("validates one candidate into the exact frozen Transaction shape", () => {
    const { transactions, errors } = parseTransactionDocument([candidate("Page 1")]);
    expect(errors).toEqual([]);
    expect(transactions).toHaveLength(1);
    expect(transactions[0]).toEqual({
      transaction_id: "tx_demo_001",
      customer_id: "cust_demo_001",
      account_id: "acc_2824",
      card_id: "card_1409",
      merchant_id: "merch_demo_electronics",
      amount: "499.99",
      currency: "USD",
      timestamp: "2026-09-13T14:00:00Z",
      payment_rail: "CARD_CNP",
      direction: "OUTGOING",
      authorization_stage: "PRE_AUTH",
      device_id: "dev_demo_99",
      ip_address: "198.51.100.88",
      geo: { lat: "25.7617", lon: "-80.1918", country: "USA" },
      channel: "WEB",
      merchant_category: "electronics",
      card_present: false,
    });
  });

  it("rejects a candidate missing a required field, with a specific reason", () => {
    const { transactions, errors } = parseTransactionDocument([candidate("Page 1", {}, ["merchant_id"])]);
    expect(transactions).toEqual([]);
    expect(errors).toHaveLength(1);
    expect(errors[0].recordLabel).toBe("Page 1");
    expect(errors[0].reason).toMatch(/merchant_id/);
  });

  it("rejects an invalid enum value instead of guessing", () => {
    const { errors } = parseTransactionDocument([candidate("Page 1", { channel: "CARRIER_PIGEON" })]);
    expect(errors).toHaveLength(1);
    expect(errors[0].reason).toMatch(/channel/);
  });

  it("rejects an invalid amount instead of guessing", () => {
    const { errors } = parseTransactionDocument([candidate("Page 1", { amount: "free" })]);
    expect(errors).toHaveLength(1);
    expect(errors[0].reason).toMatch(/amount/);
  });

  it("always supplies the fixed payment_rail/direction constants, regardless of any raw fields present", () => {
    const { transactions } = parseTransactionDocument([candidate("Page 1")]);
    expect(transactions[0].payment_rail).toBe("CARD_CNP");
    expect(transactions[0].direction).toBe("OUTGOING");
  });

  it("parses 25 candidates with 25 unique IDs", () => {
    const candidates = Array.from({ length: 25 }, (_, i) => candidate(`Page ${i + 1}`, { transaction_id: `tx_demo_${i + 1}` }));
    const { transactions, errors } = parseTransactionDocument(candidates);
    expect(errors).toEqual([]);
    expect(transactions).toHaveLength(25);
    expect(new Set(transactions.map((t) => t.transaction_id)).size).toBe(25);
  });

  it("rejects a duplicate transaction_id across candidates", () => {
    const { transactions, errors } = parseTransactionDocument([candidate("Page 1"), candidate("Page 2")]);
    expect(transactions).toHaveLength(1);
    expect(errors).toHaveLength(1);
    expect(errors[0].reason).toMatch(/Duplicate transaction_id/);
  });

  it("keeps parsing valid candidates after a malformed one", () => {
    const { transactions, errors } = parseTransactionDocument([
      candidate("Page 1", {}, ["amount"]),
      candidate("Page 2", { transaction_id: "tx_demo_002" }),
    ]);
    expect(transactions).toHaveLength(1);
    expect(transactions[0].transaction_id).toBe("tx_demo_002");
    expect(errors).toHaveLength(1);
  });

  it("reports a clear error when no candidates were found at all", () => {
    const { transactions, errors } = parseTransactionDocument([]);
    expect(transactions).toEqual([]);
    expect(errors).toHaveLength(1);
  });
});

describe("extractRecordCandidates: unsupported file types", () => {
  it("rejects an unsupported file type with a clean error, not a crash", async () => {
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    await expect(extractRecordCandidates(file)).rejects.toThrow(UnsupportedFileTypeError);
  });

  it("reports the legacy .doc limitation explicitly instead of silently mis-parsing it", async () => {
    const file = new File(["hello"], "old.doc", { type: "application/msword" });
    await expect(extractRecordCandidates(file)).rejects.toThrow(/legacy \.doc/i);
  });
});

/**
 * Regression tests for the actual PDF.js extraction bug: the real demo PDFs
 * render each transaction as a borderless two-column label/value grid (no
 * "TRANSACTION n" marker, no "===", no colon between label and value --
 * confirmed by inspecting pdfjs-dist's real getTextContent() output against
 * the three actual demo files). These fixtures reproduce that exact shape
 * (verified x/y positions, item text) via a mocked pdfjs-dist so the
 * regression is committed and doesn't depend on external binary files.
 */
function pdfToken(text: string, x: number, y: number) {
  return { str: text, transform: [1, 0, 0, 1, x, y] };
}

/** One full two-column record, laid out exactly like the real PDFs: labels
 * at x=60.3/x=295.6, values at x=145.3/x=394.8, one row per pair, 20-22pt
 * row spacing. */
function realTransactionRowItems(startY: number, values: Record<string, string>) {
  const rows: [string, string, string, string][] = [
    ["transaction_id", values.transaction_id, "customer_id", values.customer_id],
    ["account_id", values.account_id, "card_id", values.card_id],
    ["merchant_id", values.merchant_id, "merchant_category", values.merchant_category],
    ["amount", values.amount, "currency", values.currency],
    ["timestamp", values.timestamp, "payment_rail", "CARD_CNP"],
    ["direction", "OUTGOING", "authorization_stage", values.authorization_stage],
    ["device_id", values.device_id, "ip_address", values.ip_address],
    ["geo.lat", values.geo_lat, "geo.lon", values.geo_lon],
    ["geo.country", values.geo_country, "channel", values.channel],
  ];
  const items = [];
  let y = startY;
  for (const [leftLabel, leftValue, rightLabel, rightValue] of rows) {
    items.push(pdfToken(leftLabel, 60.27559, y), pdfToken(leftValue, 145.31496, y));
    items.push(pdfToken(rightLabel, 295.55119, y), pdfToken(rightValue, 394.76379, y));
    y -= 22;
  }
  items.push(pdfToken("card_present", 60.27559, y), pdfToken(values.card_present, 145.31496, y));
  return items;
}

const REAL_SHAPE_VALUES = {
  transaction_id: "tx_demo_clean_single_001",
  customer_id: "cust_demo_established_01",
  account_id: "acc_2824",
  card_id: "card_1409",
  merchant_id: "merch_demo_grocery_01",
  merchant_category: "grocery",
  amount: "75.00",
  currency: "USD",
  timestamp: "2026-09-18T14:05:00Z",
  authorization_stage: "PRE_AUTH",
  device_id: "dev_demo_established_01",
  ip_address: "203.0.113.24",
  geo_lat: "40.7128",
  geo_lon: "-74.006",
  geo_country: "USA",
  channel: "WEB",
  card_present: "false",
};

/** The batch file's page-1 cover/index table: column headers plus data
 * rows, all as bare values (never a recognized label in the first slot of
 * any pair) -- reproduces the real structure that must be skipped, not
 * mis-parsed as a malformed record. */
function indexPageItems() {
  const header = ["#", "Demo class", "Transaction ID", "Amount", "Merchant", "Customer", "Device", "Channel"];
  const row1 = ["1", "CLEAN", "tx_demo_batch_clean_01", "42.50 USD", "merch_demo_grocery_01", "cust_demo_established_01", "dev_demo_established_01", "WEB"];
  const items = [];
  let x = 20;
  for (const text of header) {
    items.push(pdfToken(text, x, 687.5));
    x += 60;
  }
  x = 20;
  for (const text of row1) {
    items.push(pdfToken(text, x, 669.8));
    x += 60;
  }
  return items;
}

function mockPdfWithPages(pages: ReturnType<typeof pdfToken>[][]) {
  return {
    getDocument: () => ({
      promise: Promise.resolve({
        numPages: pages.length,
        getPage: (n: number) =>
          Promise.resolve({
            getTextContent: () => Promise.resolve({ items: pages[n - 1] }),
          }),
      }),
    }),
    GlobalWorkerOptions: {},
  };
}

describe("extractRecordCandidates: real PDF.js output shape (regression)", () => {
  it("recognizes a two-column label/value grid page with no colon and no TRANSACTION marker", async () => {
    vi.resetModules();
    vi.doMock("pdfjs-dist", () => mockPdfWithPages([realTransactionRowItems(702.4047, REAL_SHAPE_VALUES)]));
    const { extractRecordCandidates: freshExtract } = await import("./documentParser");

    const file = new File(["irrelevant"], "sentinel_clean_transaction.pdf", { type: "application/pdf" });
    const candidates = await freshExtract(file);

    expect(candidates).toHaveLength(1);
    expect(candidates[0].fields.transaction_id).toBe("tx_demo_clean_single_001");
    expect(candidates[0].fields.geo_lat).toBe("40.7128"); // "geo.lat" label normalized, no colon involved
    vi.doUnmock("pdfjs-dist");
  });

  it("skips a cover/index page with zero recognized field labels instead of treating it as a malformed record", async () => {
    vi.resetModules();
    vi.doMock("pdfjs-dist", () => mockPdfWithPages([indexPageItems(), realTransactionRowItems(774.7433, REAL_SHAPE_VALUES)]));
    const { extractRecordCandidates: freshExtract, parseTransactionDocument: freshParse } = await import("./documentParser");

    const file = new File(["irrelevant"], "sentinel_batch_25_transactions.pdf", { type: "application/pdf" });
    const candidates = await freshExtract(file);
    const { transactions, errors } = freshParse(candidates);

    expect(candidates).toHaveLength(1); // the index page contributed nothing
    expect(transactions).toHaveLength(1);
    expect(errors).toEqual([]);
    vi.doUnmock("pdfjs-dist");
  });

  it("extracts a 25-page batch (plus a leading index page) into exactly 25 unique transactions", async () => {
    const pages = [
      indexPageItems(),
      ...Array.from({ length: 25 }, (_, i) =>
        realTransactionRowItems(774.7433, { ...REAL_SHAPE_VALUES, transaction_id: `tx_demo_batch_${i + 1}` }),
      ),
    ];
    vi.resetModules();
    vi.doMock("pdfjs-dist", () => mockPdfWithPages(pages));
    const { extractRecordCandidates: freshExtract, parseTransactionDocument: freshParse } = await import("./documentParser");

    const file = new File(["irrelevant"], "sentinel_batch_25_transactions.pdf", { type: "application/pdf" });
    const candidates = await freshExtract(file);
    const { transactions, errors } = freshParse(candidates);

    expect(transactions).toHaveLength(25);
    expect(errors).toEqual([]);
    expect(new Set(transactions.map((t) => t.transaction_id)).size).toBe(25);
    for (const t of transactions) {
      for (const key of Object.keys(t)) expect(t[key as keyof typeof t]).not.toBeUndefined();
    }
    vi.doUnmock("pdfjs-dist");
  });

  it("rejects a page whose two-column grid is missing a required field", async () => {
    // Drop the whole merchant_id label+value pair (not just one token) --
    // a single stray dropped token would corrupt row pairing itself, which
    // is a different (and separately covered) failure mode.
    const items = realTransactionRowItems(702.4047, REAL_SHAPE_VALUES).filter(
      (item) => item.str !== "merchant_id" && item.str !== "merch_demo_grocery_01",
    );
    vi.resetModules();
    vi.doMock("pdfjs-dist", () => mockPdfWithPages([items]));
    const { extractRecordCandidates: freshExtract, parseTransactionDocument: freshParse } = await import("./documentParser");

    const file = new File(["irrelevant"], "sentinel_fraud_transaction.pdf", { type: "application/pdf" });
    const candidates = await freshExtract(file);
    const { transactions, errors } = freshParse(candidates);

    expect(transactions).toEqual([]);
    expect(errors).toHaveLength(1);
    expect(errors[0].reason).toMatch(/merchant_id/);
    vi.doUnmock("pdfjs-dist");
  });
});
