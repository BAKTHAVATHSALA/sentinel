import * as pdfjsLib from "pdfjs-dist";
import type { TextItem } from "pdfjs-dist/types/src/display/api";
// eslint-disable-next-line import/no-unresolved -- Vite's ?url suffix resolves to the built worker asset.
import pdfjsWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import mammoth from "mammoth";
import type { Transaction } from "./types";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl;

/**
 * Deterministic, non-AI document input adapter (docs/transaction_document_format.md).
 *
 * The real demo PDFs render each transaction as a borderless two-column
 * label/value grid (one page per transaction; a leading summary/index page
 * in the batch file has no label/value pairs at all) -- there is no literal
 * "TRANSACTION n" marker, no "===" terminator, and no colon between a label
 * and its value in the extracted text. Labels and values are simply two
 * adjacent text runs at fixed positions, confirmed by inspecting pdfjs-dist's
 * actual getTextContent() output against the three real demo files (see
 * project history for the diagnostic dump). Parsing is still fully
 * deterministic: every recognized field name comes from the fixed,
 * closed vocabulary below -- nothing is inferred from unrecognized text,
 * and a page/table with zero recognized fields is treated as a non-record
 * page (e.g. the batch's cover/index page), not silently repaired.
 */

export interface ParsedRecordError {
  recordLabel: string;
  reason: string;
}

export interface ParseResult {
  transactions: Transaction[];
  errors: ParsedRecordError[];
}

/** One candidate record's raw recognized fields, before validation --
 * one PDF page, or one DOCX table, with at least one recognized label. */
export interface RecordCandidate {
  recordLabel: string;
  fields: Record<string, string>;
}

const REQUIRED_STRING_FIELDS = [
  "transaction_id",
  "customer_id",
  "account_id",
  "card_id",
  "merchant_id",
  "device_id",
  "ip_address",
  "merchant_category",
] as const;

/** The closed field-name vocabulary. `payment_rail`/`direction` are
 * recognized (so the two-column pairing doesn't misalign around them) but
 * deliberately never read into the output -- V1's schema has exactly one
 * valid value for each, supplied as fixed constants below, regardless of
 * what text (if any) appears next to those labels in the source document. */
const KNOWN_LABEL_ALIASES: Record<string, string> = {
  transaction_id: "transaction_id",
  customer_id: "customer_id",
  account_id: "account_id",
  card_id: "card_id",
  merchant_id: "merchant_id",
  merchant_category: "merchant_category",
  amount: "amount",
  currency: "currency",
  timestamp: "timestamp",
  authorization_stage: "authorization_stage",
  device_id: "device_id",
  ip_address: "ip_address",
  channel: "channel",
  card_present: "card_present",
  "geo.lat": "geo_lat",
  geo_lat: "geo_lat",
  "geo.lon": "geo_lon",
  geo_lon: "geo_lon",
  "geo.country": "geo_country",
  geo_country: "geo_country",
  payment_rail: "payment_rail",
  direction: "direction",
};

/** Pairs adjacent row tokens into (label, value) and keeps only pairs whose
 * first token is a recognized field label -- an unrecognized label (a page
 * title, a table header cell, a footer sentence, ...) contributes nothing,
 * rather than being guessed at. */
function fieldsFromRowTokens(tokensInReadingOrder: string[]): Record<string, string> {
  const fields: Record<string, string> = {};
  for (let i = 0; i + 1 < tokensInReadingOrder.length; i += 2) {
    const rawLabel = tokensInReadingOrder[i].trim().toLowerCase();
    const value = tokensInReadingOrder[i + 1].trim();
    const normalizedKey = KNOWN_LABEL_ALIASES[rawLabel];
    if (normalizedKey && value) fields[normalizedKey] = value;
  }
  return fields;
}

function mergeFields(base: Record<string, string>, addition: Record<string, string>): void {
  for (const [key, value] of Object.entries(addition)) base[key] = value;
}

function validateRecord(recordLabel: string, fields: Record<string, string>): Transaction | ParsedRecordError {
  for (const field of REQUIRED_STRING_FIELDS) {
    if (!fields[field]) return { recordLabel, reason: `Missing required field "${field}"` };
  }

  const amountRaw = fields.amount;
  if (!amountRaw || !/^\d+(\.\d+)?$/.test(amountRaw)) {
    return { recordLabel, reason: `Missing or invalid "amount" (expected a decimal number, got ${amountRaw ?? "nothing"})` };
  }

  const currency = fields.currency;
  if (!currency || !/^[A-Za-z]{3}$/.test(currency)) {
    return { recordLabel, reason: `Missing or invalid "currency" (expected a 3-letter code, got ${currency ?? "nothing"})` };
  }

  const timestamp = fields.timestamp;
  if (!timestamp || Number.isNaN(Date.parse(timestamp))) {
    return { recordLabel, reason: `Missing or invalid "timestamp" (expected ISO 8601, got ${timestamp ?? "nothing"})` };
  }

  const authorizationStage = fields.authorization_stage;
  if (!authorizationStage || !["PRE_AUTH", "AUTH", "SETTLED"].includes(authorizationStage.toUpperCase())) {
    return {
      recordLabel,
      reason: `Missing or invalid "authorization_stage" (expected PRE_AUTH, AUTH, or SETTLED, got ${authorizationStage ?? "nothing"})`,
    };
  }

  const channel = fields.channel;
  if (!channel || !["WEB", "MOBILE"].includes(channel.toUpperCase())) {
    return { recordLabel, reason: `Missing or invalid "channel" (expected WEB or MOBILE, got ${channel ?? "nothing"})` };
  }

  const cardPresentRaw = fields.card_present;
  if (!cardPresentRaw || !["true", "false"].includes(cardPresentRaw.toLowerCase())) {
    return { recordLabel, reason: `Missing or invalid "card_present" (expected true or false, got ${cardPresentRaw ?? "nothing"})` };
  }

  const geoLat = fields.geo_lat;
  const geoLon = fields.geo_lon;
  const geoCountry = fields.geo_country;
  if (!geoLat || Number.isNaN(Number(geoLat))) return { recordLabel, reason: `Missing or invalid "geo.lat"` };
  if (!geoLon || Number.isNaN(Number(geoLon))) return { recordLabel, reason: `Missing or invalid "geo.lon"` };
  if (!geoCountry) return { recordLabel, reason: `Missing required field "geo.country"` };

  return {
    transaction_id: fields.transaction_id,
    customer_id: fields.customer_id,
    account_id: fields.account_id,
    card_id: fields.card_id,
    merchant_id: fields.merchant_id,
    amount: amountRaw,
    currency: currency.toUpperCase(),
    timestamp,
    payment_rail: "CARD_CNP",
    direction: "OUTGOING",
    authorization_stage: authorizationStage.toUpperCase() as Transaction["authorization_stage"],
    device_id: fields.device_id,
    ip_address: fields.ip_address,
    geo: { lat: geoLat, lon: geoLon, country: geoCountry },
    channel: channel.toUpperCase() as Transaction["channel"],
    merchant_category: fields.merchant_category,
    card_present: cardPresentRaw.toLowerCase() === "true",
  };
}

/** Validates each candidate independently and checks for duplicate
 * transaction_id values across the whole document. Never throws -- one bad
 * record collects an error and parsing continues with the rest. */
export function parseTransactionDocument(candidates: RecordCandidate[]): ParseResult {
  const transactions: Transaction[] = [];
  const errors: ParsedRecordError[] = [];
  const seenIds = new Set<string>();

  for (const candidate of candidates) {
    const result = validateRecord(candidate.recordLabel, candidate.fields);
    if ("reason" in result) {
      errors.push(result);
    } else if (seenIds.has(result.transaction_id)) {
      errors.push({ recordLabel: candidate.recordLabel, reason: `Duplicate transaction_id "${result.transaction_id}" within this document` });
    } else {
      seenIds.add(result.transaction_id);
      transactions.push(result);
    }
  }

  if (candidates.length === 0) {
    errors.push({ recordLabel: "(document)", reason: "No transaction records found in this document" });
  }

  return { transactions, errors };
}

export class UnsupportedFileTypeError extends Error {}

interface PositionedToken {
  x: number;
  y: number;
  text: string;
}

/** Groups tokens into visual rows by Y (tokens within 2pt are the same
 * row), sorts each row left-to-right by X, and pairs them into fields. */
function fieldsFromPositionedTokens(tokens: PositionedToken[]): Record<string, string> {
  const rowsByY: { y: number; tokens: PositionedToken[] }[] = [];
  for (const token of tokens) {
    if (!token.text) continue;
    let row = rowsByY.find((r) => Math.abs(r.y - token.y) <= 2);
    if (!row) {
      row = { y: token.y, tokens: [] };
      rowsByY.push(row);
    }
    row.tokens.push(token);
  }

  const fields: Record<string, string> = {};
  for (const row of rowsByY) {
    row.tokens.sort((a, b) => a.x - b.x);
    mergeFields(fields, fieldsFromRowTokens(row.tokens.map((t) => t.text)));
  }
  return fields;
}

async function extractPdfCandidates(file: File): Promise<RecordCandidate[]> {
  const buffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: buffer }).promise;
  const candidates: RecordCandidate[] = [];

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
    const page = await pdf.getPage(pageNumber);
    const content = await page.getTextContent();
    const tokens: PositionedToken[] = content.items
      .filter((item): item is TextItem => "str" in item && "transform" in item)
      .map((item) => ({ x: item.transform[4], y: item.transform[5], text: item.str.trim() }));

    const fields = fieldsFromPositionedTokens(tokens);
    if (Object.keys(fields).length > 0) {
      candidates.push({ recordLabel: `Page ${pageNumber}`, fields });
    }
  }
  return candidates;
}

async function extractDocxCandidates(file: File): Promise<RecordCandidate[]> {
  const buffer = await file.arrayBuffer();
  const { value: html } = await mammoth.convertToHtml({ arrayBuffer: buffer });
  const doc = new DOMParser().parseFromString(html, "text/html");
  const candidates: RecordCandidate[] = [];

  const tables = Array.from(doc.querySelectorAll("table"));
  tables.forEach((table, tableIndex) => {
    const fields: Record<string, string> = {};
    for (const row of Array.from(table.querySelectorAll("tr"))) {
      const cellTexts = Array.from(row.querySelectorAll("td, th")).map((cell) => (cell.textContent ?? "").trim());
      mergeFields(fields, fieldsFromRowTokens(cellTexts));
    }
    if (Object.keys(fields).length > 0) {
      candidates.push({ recordLabel: `Table ${tableIndex + 1}`, fields });
    }
  });
  return candidates;
}

/** Extracts record candidates from an uploaded .pdf or .docx file. Legacy
 * .doc is deliberately not supported -- reliable text extraction for the
 * old binary format needs a separate, less dependable dependency;
 * reporting that limitation is preferable to silently mis-parsing it. */
export async function extractRecordCandidates(file: File): Promise<RecordCandidate[]> {
  const name = file.name.toLowerCase();

  if (name.endsWith(".pdf") || file.type === "application/pdf") {
    return extractPdfCandidates(file);
  }

  if (name.endsWith(".docx") || file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document") {
    return extractDocxCandidates(file);
  }

  if (name.endsWith(".doc")) {
    throw new UnsupportedFileTypeError(
      "Legacy .doc files are not supported -- reliable text extraction for the old binary Word format would need a separate, less dependable dependency. Please use PDF or .docx.",
    );
  }

  throw new UnsupportedFileTypeError(`Unsupported file type "${file.name}". Please upload a PDF or DOCX file.`);
}
