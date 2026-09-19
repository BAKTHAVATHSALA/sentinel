# Sentinel V1 Transaction Document Format (Transaction Console upload)

This describes the actual, verified layout the public Transaction
Investigation Console's client-side parser (`ui/src/lib/documentParser.ts`)
understands. **This document was corrected after inspecting pdfjs-dist's
real `getTextContent()` output against the three actual demo files
(`sentinel_clean_transaction.pdf`, `sentinel_fraud_transaction.pdf`,
`sentinel_batch_25_transactions.pdf`)** -- an earlier version of this
document assumed a colon-delimited, line-based `TRANSACTION n` / `===`
convention that the real files never actually used. The parser now matches
what these files actually contain; nothing about the three files themselves
needs to change.

There is no OCR, no AI extraction, and no field-guessing: every field below
must be present as a recognized label paired with a value, or the record is
rejected with a clear error naming the missing/invalid field.

## The real layout: a borderless two-column label/value grid

Each transaction is rendered as a two-column table of label/value pairs
(no visible borders, no literal colon character between label and value --
label and value are simply two adjacent text runs at fixed horizontal
positions). One PDF **page** is one transaction record. Example, exactly as
`sentinel_clean_transaction.pdf` actually renders it:

```
transaction_id          tx_demo_clean_single_001    customer_id           cust_demo_established_01
account_id              acc_2824                    card_id               card_1409
merchant_id             merch_demo_grocery_01       merchant_category     grocery
amount                  75.00                       currency              USD
timestamp               2026-09-18T14:05:00Z        payment_rail          CARD_CNP
direction               OUTGOING                    authorization_stage   PRE_AUTH
device_id               dev_demo_established_01     ip_address            203.0.113.24
geo.lat                 40.7128                     geo.lon               -74.006
geo.country             USA                         channel               WEB
card_present            false
```

Rules:

- **One PDF page = one transaction record.** A single-transaction file
  (`sentinel_clean_transaction.pdf`, `sentinel_fraud_transaction.pdf`) has
  one page. The batch file has 26 pages: page 1 is a human-readable
  cover/index table (transaction count, "clean"/"suspicious" composition
  labels) and is **not** parsed as a record -- it contains none of the
  recognized field labels below, so it is skipped automatically, not
  guessed at. Pages 2-26 are the 25 actual records.
- Labels and values are recognized by **position within a row**, not by a
  colon: on each visual row, tokens are read left to right and grouped into
  (label, value) pairs. A token is only treated as a label if it exactly
  matches one of the field names below (case-insensitive) -- any
  unrecognized text (a page title, a table header cell, a footer sentence)
  simply contributes nothing.
- The nested `geo` object's fields are labeled `geo.lat`, `geo.lon`,
  `geo.country` (dot notation, not underscore).
- `payment_rail` and `direction` **do** appear in the real documents
  (unlike what an earlier version of this spec assumed) -- the parser
  recognizes them so row-pairing stays correct, but **always** supplies the
  fixed V1 constants (`CARD_CNP` / `OUTGOING`) in the submitted transaction
  regardless of what text sits next to those labels in the source document.

## Field validation

| Field | Format |
|---|---|
| `transaction_id`, `customer_id`, `account_id`, `card_id`, `merchant_id`, `device_id`, `ip_address`, `merchant_category` | non-empty string |
| `amount` | decimal number, e.g. `499.99` |
| `currency` | 3-letter code, e.g. `USD` |
| `timestamp` | ISO 8601, e.g. `2026-09-13T14:00:00Z` |
| `authorization_stage` | exactly one of `PRE_AUTH`, `AUTH`, `SETTLED` |
| `geo.lat`, `geo.lon` | decimal numbers |
| `geo.country` | string, e.g. `USA` |
| `channel` | exactly one of `WEB`, `MOBILE` |
| `card_present` | exactly `true` or `false` (lowercase) |

Any field failing its format, or missing entirely, rejects that one page's
record with a specific error naming the field and the page number. In the
batch file, other valid pages are still parsed and offered for
investigation -- one bad page does not discard the whole file.

## Batch file composition

`sentinel_batch_25_transactions.pdf`: 25 record pages, each with its own
unique `transaction_id`. A duplicate `transaction_id` across two pages in
the same upload is rejected at validation time as a document authoring
error (separate from the existing backend idempotency behavior, which
handles a duplicate against a *previously submitted* transaction).

Whether a given transaction is "clean" or "suspicious" in the cover page's
composition summary is descriptive metadata only -- it has no effect on
parsing and is never shown in the UI as a pre-determined outcome. Only the
real `POST /transactions` response decides `AUTO_RESOLVE` vs
`HUMAN_REVIEW`.

## DOCX

`.docx` files are parsed by looking for the equivalent structure in a real
Word table: each `<table>` in the document is treated as one candidate
record, with table rows read the same left-to-right (label, value) pairing
as the PDF columns. This has not been verified against a real `.docx` demo
file (none has been provided) -- it is a best-effort, structurally
consistent extension of the verified PDF logic, not something to rely on
without testing against an actual sample first.
