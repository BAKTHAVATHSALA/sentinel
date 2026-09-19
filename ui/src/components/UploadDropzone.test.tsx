import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UploadDropzone } from "./UploadDropzone";
import * as documentParser from "../lib/documentParser";
import type { Transaction } from "../lib/types";

function makeTransaction(id: string): Transaction {
  return {
    transaction_id: id,
    customer_id: "cust",
    account_id: "acc",
    card_id: "card",
    merchant_id: "merch",
    amount: "10.00",
    currency: "USD",
    timestamp: "2026-09-13T14:00:00Z",
    payment_rail: "CARD_CNP",
    direction: "OUTGOING",
    authorization_stage: "PRE_AUTH",
    device_id: "dev",
    ip_address: "1.2.3.4",
    geo: { lat: "0", lon: "0", country: "USA" },
    channel: "WEB",
    merchant_category: "electronics",
    card_present: false,
  };
}

describe("UploadDropzone", () => {
  it("parses a valid file and reports the transactions to the parent", async () => {
    vi.spyOn(documentParser, "extractRecordCandidates").mockResolvedValue([{ recordLabel: "Page 1", fields: {} }]);
    vi.spyOn(documentParser, "parseTransactionDocument").mockReturnValue({
      transactions: [makeTransaction("tx_1")],
      errors: [],
    });
    const onParsed = vi.fn();
    const user = userEvent.setup();
    render(<UploadDropzone onParsed={onParsed} />);

    const file = new File(["irrelevant"], "sentinel_clean_transaction.pdf", { type: "application/pdf" });
    await user.upload(screen.getByTestId("file-input"), file);

    await waitFor(() => expect(onParsed).toHaveBeenCalledWith([makeTransaction("tx_1")], [], "sentinel_clean_transaction.pdf"));
  });

  it("shows a clean error and does not call onParsed when extraction fails", async () => {
    vi.spyOn(documentParser, "extractRecordCandidates").mockRejectedValue(
      new documentParser.UnsupportedFileTypeError("Unsupported file type"),
    );
    const onParsed = vi.fn();
    const user = userEvent.setup();
    render(<UploadDropzone onParsed={onParsed} />);

    // Named/typed to pass the input's accept filter (drag-and-drop bypasses
    // it entirely anyway) -- the mocked extractRecordCandidates is what
    // actually determines this test's failure path, matching a real
    // unreadable file.
    const file = new File(["irrelevant"], "corrupt.pdf", { type: "application/pdf" });
    await user.upload(screen.getByTestId("file-input"), file);

    expect(await screen.findByText("Unsupported file type")).toBeInTheDocument();
    expect(onParsed).not.toHaveBeenCalled();
  });

  it("shows per-record errors and does not call onParsed when nothing valid was extracted", async () => {
    vi.spyOn(documentParser, "extractRecordCandidates").mockResolvedValue([{ recordLabel: "Page 1", fields: {} }]);
    vi.spyOn(documentParser, "parseTransactionDocument").mockReturnValue({
      transactions: [],
      errors: [{ recordLabel: "Page 1", reason: 'Missing required field "amount"' }],
    });
    const onParsed = vi.fn();
    const user = userEvent.setup();
    render(<UploadDropzone onParsed={onParsed} />);

    const file = new File(["irrelevant"], "broken.pdf", { type: "application/pdf" });
    await user.upload(screen.getByTestId("file-input"), file);

    expect(await screen.findByText(/Page 1/)).toBeInTheDocument();
    expect(onParsed).not.toHaveBeenCalled();
  });
});
