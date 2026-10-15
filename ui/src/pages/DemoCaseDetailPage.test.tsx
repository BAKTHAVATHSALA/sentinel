import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoCaseDetailPage } from "./DemoCaseDetailPage";
import * as demoApi from "../lib/demoApi";
import type { CaseDocument } from "../lib/types";

function mockDemoCaseDoc(overrides: Partial<CaseDocument> = {}): CaseDocument {
  return {
    case_id: "demo_test_case_01",
    transaction_id: "tx_demo_01",
    state: "HUMAN_REVIEW",
    created_at: "2026-09-21T00:00:00Z",
    updated_at: "2026-09-21T00:00:00Z",
    transaction: {
      transaction_id: "tx_demo_01",
      customer_id: "cust_demo",
      account_id: "acc_demo",
      card_id: "card_demo",
      merchant_id: "merch_electronics",
      amount: "1499.00",
      currency: "USD",
      timestamp: "2026-09-21T00:00:00Z",
      payment_rail: "CARD_CNP",
      direction: "OUTGOING",
      authorization_stage: "PRE_AUTH",
      device_id: "dev_new",
      ip_address: "198.51.100.88",
      geo: { lat: "34.0522", lon: "-118.2437", country: "USA" },
      channel: "WEB",
      merchant_category: "electronics",
      card_present: false,
    },
    detection: {
      case_id: "demo_test_case_01",
      transaction_id: "tx_demo_01",
      risk_score: "0.89",
      risk_band: "HIGH",
      anomaly_tags: ["NEW_DEVICE", "MERCHANT_RISK"],
      detection_reasons: ["Unrecognized device", "Merchant risk"],
      model_name: "baseline-rf-v1",
      model_version: "1.1.0",
      detected_at: "2026-09-21T00:00:00Z",
    },
    evidence_bundle: {
      evidence_bundle_id: "bundle_01",
      case_id: "demo_test_case_01",
      facts: [
        {
          fact_id: "fact_dev_link",
          type: "DEVICE_LINKAGE",
          subject_id: "dev_new",
          value: { summary: "Device linked across accounts" },
          source_tool: "get_device_history",
          source_record_id: "rec_01",
          observed_at: "2026-09-21T00:00:00Z",
          retrieved_at: "2026-09-21T00:00:00Z",
          quality: "VERIFIED",
        },
      ],
      tools_called: ["get_device_history"],
      required_tools: ["get_device_history"],
      completeness: "COMPLETE",
      missing_required_evidence: [],
      conflicts: [],
      started_at: "2026-09-21T00:00:00Z",
      completed_at: "2026-09-21T00:00:00Z",
    },
    findings: {
      findings_id: "find_01",
      case_id: "demo_test_case_01",
      risk_assessment: "HIGH",
      summary: "High confidence fraud assessment.",
      supporting_factors: [
        {
          statement: "Device link confirmed.",
          fact_ids: ["fact_dev_link"],
          materiality: "HIGH",
        },
      ],
      counter_factors: [],
      evidence_gaps: [],
      evidence_citations: [{ claim_id: "c1", fact_ids: ["fact_dev_link"] }],
      recommended_disposition: "ESCALATE",
      generated_at: "2026-09-21T00:00:00Z",
      model_name: "gemini-2.0-flash",
      model_version: "2.0",
      prompt_version: "1.0.0",
    },
    robustness: {
      robustness_id: "rob_01",
      case_id: "demo_test_case_01",
      classification: "ROBUST",
      fragile_factor_id: null,
      method: "FAST_PATH",
      evaluated_at: "2026-09-21T00:00:00Z",
    },
    policy_decision: {
      decision_id: "pol_01",
      case_id: "demo_test_case_01",
      outcome: "ESCALATE",
      rule_id: "P-002",
      rule_version: "1.0.0",
      reasons: ["High risk score holds authorization pending human review."],
      inputs_snapshot: {},
      evaluated_at: "2026-09-21T00:00:00Z",
    },
    assigned_analyst_id: "demo_analyst",
    final_disposition: null,
    ...overrides,
  };
}

describe("DemoCaseDetailPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders demo case detail and executes human CLEAR decision", async () => {
    const user = userEvent.setup();
    const doc = mockDemoCaseDoc();
    vi.spyOn(demoApi, "fetchDemoCase").mockResolvedValue(doc);
    const submitSpy = vi.spyOn(demoApi, "submitDemoDecision").mockResolvedValue({
      case_id: "demo_test_case_01",
      state: "FINALIZED",
      final_disposition: "CLEAR",
      assigned_analyst_id: "demo_analyst",
      target_analyst_display_name: null,
      decided_at: "2026-09-21T00:05:00Z",
      idempotent_replay: false,
    });

    render(
      <MemoryRouter initialEntries={["/demo/case/demo_test_case_01"]}>
        <Routes>
          <Route path="/demo/case/:caseId" element={<DemoCaseDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Demo Analyst Decision Authority")).toBeInTheDocument();
      expect(screen.getByText("Clear Transaction")).toBeInTheDocument();
      expect(screen.getByText("Block & Hold")).toBeInTheDocument();
    });

    // Check evidence acknowledged checkbox
    const checkbox = screen.getByRole("checkbox");
    await user.click(checkbox);

    // Click Clear Transaction
    const clearBtn = screen.getByText("Clear Transaction");
    await user.click(clearBtn);

    // Type reason
    const textarea = screen.getByPlaceholderText(/Document justification/);
    await user.type(textarea, "Verified via customer confirmation");

    // Click confirm
    const confirmBtn = screen.getByText("Confirm Clear");
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(submitSpy).toHaveBeenCalledWith("demo_test_case_01", expect.objectContaining({
        action: "CLEAR",
        reason: "Verified via customer confirmation",
        evidence_acknowledged: true,
      }));
      expect(screen.getByText(/Case Cleared/i)).toBeInTheDocument();
    });
  });

  it("renders demo case detail and executes ESCALATE_SENIOR decision", async () => {
    const user = userEvent.setup();
    const doc = mockDemoCaseDoc({
      available_seniors: [
        { uid: "senior_demo_01", display_name: "Elena Cho (Senior Fraud Analyst)", email: "elena@sentinel.demo" },
      ],
    });
    vi.spyOn(demoApi, "fetchDemoCase").mockResolvedValue(doc);
    const submitSpy = vi.spyOn(demoApi, "submitDemoDecision").mockResolvedValue({
      case_id: "demo_test_case_01",
      state: "HUMAN_REVIEW",
      final_disposition: null,
      assigned_analyst_id: "senior_demo_01",
      target_analyst_display_name: "Elena Cho (Senior Fraud Analyst)",
      decided_at: "2026-09-21T00:05:00Z",
      idempotent_replay: false,
    });

    render(
      <MemoryRouter initialEntries={["/demo/case/demo_test_case_01"]}>
        <Routes>
          <Route path="/demo/case/:caseId" element={<DemoCaseDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Escalate to Senior Analyst")).toBeInTheDocument();
    });

    // Check evidence acknowledged checkbox
    const checkbox = screen.getByRole("checkbox");
    await user.click(checkbox);

    // Click Escalate
    const escalateBtn = screen.getByText("Escalate to Senior Analyst");
    await user.click(escalateBtn);

    // Type reason
    const textarea = screen.getByPlaceholderText(/Document justification/);
    await user.type(textarea, "Complex device link requires senior review");

    // Click confirm
    const confirmBtn = screen.getByText("Confirm Escalation");
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(submitSpy).toHaveBeenCalledWith("demo_test_case_01", expect.objectContaining({
        action: "ESCALATE_SENIOR",
        reason: "Complex device link requires senior review",
        evidence_acknowledged: true,
        target_analyst_id: "senior_demo_01",
      }));
      expect(screen.getByText("Case Escalated Successfully")).toBeInTheDocument();
      expect(screen.getByText("Elena Cho (Senior Fraud Analyst)")).toBeInTheDocument();
      expect(screen.getByText(/Assigned to:/)).toBeInTheDocument();
      expect(screen.getByText("Back to Transaction Console")).toBeInTheDocument();
    });
  });
});
