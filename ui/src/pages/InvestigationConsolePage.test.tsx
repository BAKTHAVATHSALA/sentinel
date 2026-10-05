import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { InvestigationConsolePage } from "./InvestigationConsolePage";
import * as api from "../lib/api";
import { ApiError } from "../lib/api";
import type { Transaction } from "../lib/types";

function makeTransaction(id: string): Transaction {
  return {
    transaction_id: id,
    customer_id: "cust_demo_1",
    account_id: "acc_2824",
    card_id: "card_1409",
    merchant_id: "merch_demo_electronics_risky",
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
  };
}

vi.mock("../components/UploadDropzone", () => ({
  UploadDropzone: ({ onParsed }: { onParsed: (t: Transaction[], e: unknown[], name: string) => void }) => (
    <div>
      <button onClick={() => onParsed([makeTransaction("tx_single")], [], "single.pdf")}>Simulate single upload</button>
      <button onClick={() => onParsed([makeTransaction("tx_batch_1"), makeTransaction("tx_batch_2")], [], "batch.pdf")}>
        Simulate batch upload
      </button>
    </div>
  ),
}));

const AUTO_RESOLVE_RESULT: Awaited<ReturnType<typeof api.postTransaction>> = {
  case_id: "case_clean_0001",
  transaction_id: "tx_single",
  state: "AUTO_RESOLVED",
  outcome: null,
  rule_id: null,
  duplicate: false,
  assignment: null,
  decision_summary: {
    risk_assessment: "LOW",
    anomaly_tags: [],
    policy_rule_id: null,
    reasons: [],
    evidence_completeness: null,
    merchant_flagged: false,
  },
};

const HUMAN_REVIEW_RESULT: Awaited<ReturnType<typeof api.postTransaction>> = {
  case_id: "case_flagship_0001",
  transaction_id: "tx_single",
  state: "HUMAN_REVIEW",
  outcome: "ESCALATE",
  rule_id: "P-002",
  duplicate: false,
  decision_summary: {
    risk_assessment: "HIGH",
    anomaly_tags: ["NEW_DEVICE", "UNUSUAL_LOCATION"],
    policy_rule_id: "P-002",
    reasons: ["risk_band = HIGH (>= MEDIUM)", "findings.risk_assessment = HIGH", "evidence.completeness = COMPLETE"],
    evidence_completeness: "COMPLETE",
    merchant_flagged: false,
  },
  assignment: { analyst_name: "Priya Nair" },
};

function renderConsole() {
  return render(
    <MemoryRouter initialEntries={["/investigate"]}>
      <Routes>
        <Route path="/investigate" element={<InvestigationConsolePage />} />
        <Route path="/case/:caseId" element={<div>Case detail page opened</div>} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("InvestigationConsolePage", () => {
  it("shows the upload zone by default, with no scenario buttons, Case queue, or Sign out", () => {
    renderConsole();
    expect(screen.getByText("Transaction Investigation Console")).toBeInTheDocument();
    expect(screen.queryByText("Clean Transaction")).not.toBeInTheDocument();
    expect(screen.queryByText("Suspicious / Flagship Transaction")).not.toBeInTheDocument();
    expect(screen.queryByText("Case queue")).not.toBeInTheDocument();
    expect(screen.queryByText("Sign out")).not.toBeInTheDocument();
    expect(screen.getByText("Analyst Login")).toBeInTheDocument();
  });

  it("shows a compact single-transaction preview after parsing, not a large form", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByText("Simulate single upload"));

    expect(screen.getByText("TRANSACTION READY")).toBeInTheDocument();
    expect(screen.getByText("tx_single")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Investigate Transaction" })).toBeInTheDocument();
  });

  it("calls the real POST /transactions with the parsed transaction on Investigate", async () => {
    const postSpy = vi.spyOn(api, "postTransaction").mockResolvedValue(AUTO_RESOLVE_RESULT);
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByText("Simulate single upload"));
    await user.click(screen.getByRole("button", { name: "Investigate Transaction" }));

    await waitFor(() => expect(postSpy).toHaveBeenCalledWith(expect.objectContaining({ transaction_id: "tx_single" })));
  });

  it("polls GET /transactions/{id}/status for real progress while the investigation is running, and stops once it resolves", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let resolvePost: (value: typeof AUTO_RESOLVE_RESULT) => void;
    vi.spyOn(api, "postTransaction").mockImplementation(
      () => new Promise((resolve) => { resolvePost = resolve; }),
    );
    const statusSpy = vi.spyOn(api, "fetchTransactionStatus").mockResolvedValue({
      case_id: "case_clean_0001",
      state: "DETECTED",
      has_evidence_bundle: false,
      has_robustness: false,
      has_policy_decision: false,
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) });
    renderConsole();

    await user.click(screen.getByText("Simulate single upload"));
    await user.click(screen.getByRole("button", { name: "Investigate Transaction" }));

    await vi.advanceTimersByTimeAsync(1000);
    expect(statusSpy).toHaveBeenCalledWith("tx_single");
    const callsWhileRunning = statusSpy.mock.calls.length;
    expect(callsWhileRunning).toBeGreaterThan(0);

    resolvePost!(AUTO_RESOLVE_RESULT);
    await vi.waitFor(() => expect(screen.getByText("AUTO-RESOLVED")).toBeInTheDocument());

    await vi.advanceTimersByTimeAsync(2000);
    expect(statusSpy.mock.calls.length).toBe(callsWhileRunning); // no further polling after the real result landed

    vi.useRealTimers();
  });

  it("renders AUTO_RESOLVE with no analyst assignment", async () => {
    vi.spyOn(api, "postTransaction").mockResolvedValue(AUTO_RESOLVE_RESULT);
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByText("Simulate single upload"));
    await user.click(screen.getByRole("button", { name: "Investigate Transaction" }));

    expect(await screen.findByText("AUTO-RESOLVED")).toBeInTheDocument();
    expect(screen.getAllByText("No analyst action required.").length).toBeGreaterThan(0);
  });

  it("renders HUMAN_REVIEW with only the normal analyst's display name, no email or UID", async () => {
    vi.spyOn(api, "postTransaction").mockResolvedValue(HUMAN_REVIEW_RESULT);
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByText("Simulate single upload"));
    await user.click(screen.getByRole("button", { name: "Investigate Transaction" }));

    expect(await screen.findByText("HUMAN REVIEW")).toBeInTheDocument();
    expect(screen.getByText("Priya Nair")).toBeInTheDocument();
    expect(screen.queryByText(/@sentinel\.demo/)).not.toBeInTheDocument();
  });

  it("navigates to the existing case detail route via Open Case", async () => {
    vi.spyOn(api, "postTransaction").mockResolvedValue(HUMAN_REVIEW_RESULT);
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByText("Simulate single upload"));
    await user.click(screen.getByRole("button", { name: "Investigate Transaction" }));
    await user.click(await screen.findByRole("link", { name: "Open Case" }));

    expect(await screen.findByText("Case detail page opened")).toBeInTheDocument();
  });

  it("renders a clean error on API failure and allows retrying without re-uploading", async () => {
    vi.spyOn(api, "postTransaction").mockRejectedValue(new ApiError(404, "transaction_id matches no seeded scenario"));
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByText("Simulate single upload"));
    await user.click(screen.getByRole("button", { name: "Investigate Transaction" }));

    expect(await screen.findByText("transaction_id matches no seeded scenario")).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
  });

  it("shows the batch view when the upload produces more than one transaction", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByText("Simulate batch upload"));

    expect(screen.getByText("TRANSACTION BATCH")).toBeInTheDocument();
    expect(screen.getByText("2 transactions detected")).toBeInTheDocument();
  });

  it("returns to the upload zone after 'Upload a different file'", async () => {
    vi.spyOn(api, "postTransaction").mockResolvedValue(AUTO_RESOLVE_RESULT);
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByText("Simulate single upload"));
    await user.click(screen.getByRole("button", { name: "Investigate Transaction" }));
    await screen.findByText("AUTO-RESOLVED");
    await user.click(screen.getByRole("button", { name: "Upload a different file" }));

    expect(screen.getByText("Simulate single upload")).toBeInTheDocument();
    expect(screen.queryByText("AUTO-RESOLVED")).not.toBeInTheDocument();
  });
});
