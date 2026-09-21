import { describe, expect, it } from "vitest";
import { deriveExhibitSummary } from "./exhibitSummary";
import type { Fact } from "./types";

function fact(overrides: Partial<Fact> = {}): Fact {
  return {
    fact_id: "fact_01",
    type: "DEVICE_HISTORY",
    subject_id: "cust_1",
    value: {},
    source_tool: "get_device_history",
    source_record_id: null,
    observed_at: "2026-09-21T00:00:00Z",
    retrieved_at: "2026-09-21T00:00:00Z",
    quality: "VERIFIED",
    ...overrides,
  };
}

describe("deriveExhibitSummary", () => {
  it("device history: new device", () => {
    const result = deriveExhibitSummary(fact({ source_tool: "get_device_history", value: { known_device: false } }));
    expect(result?.conclusion).toBe("New device confirmed");
  });

  it("device history: known device", () => {
    const result = deriveExhibitSummary(fact({ source_tool: "get_device_history", value: { known_device: true } }));
    expect(result?.conclusion).toBe("Known device confirmed");
  });

  it("ip geovelocity: location differs from baseline above the 800km threshold", () => {
    const result = deriveExhibitSummary(
      fact({ source_tool: "get_ip_geovelocity", value: { distance_km: "1200.0", impossible_travel: false } }),
    );
    expect(result?.conclusion).toBe("Location differs from customer baseline");
  });

  it("ip geovelocity: location consistent with baseline under the threshold", () => {
    const result = deriveExhibitSummary(
      fact({ source_tool: "get_ip_geovelocity", value: { distance_km: "5.0", impossible_travel: false } }),
    );
    expect(result?.conclusion).toBe("Location consistent with customer baseline");
  });

  it("ip geovelocity: impossible travel takes precedence", () => {
    const result = deriveExhibitSummary(
      fact({ source_tool: "get_ip_geovelocity", value: { distance_km: "50.0", impossible_travel: true } }),
    );
    expect(result?.conclusion).toBe("Impossible travel detected");
  });

  it("behavioral baseline: amount consistent with customer behavior", () => {
    const result = deriveExhibitSummary(
      fact({ source_tool: "get_behavioral_baseline", value: { amount_deviation: "0.5", typical_amount: "120.00" } }),
    );
    expect(result?.conclusion).toBe("Amount consistent with customer behavior");
  });

  it("behavioral baseline: amount deviates from customer behavior", () => {
    const result = deriveExhibitSummary(
      fact({ source_tool: "get_behavioral_baseline", value: { amount_deviation: "6.0", typical_amount: "120.00" } }),
    );
    expect(result?.conclusion).toBe("Amount deviates from customer behavior");
  });

  it("linked entities: no supporting relationship found when both lists are empty", () => {
    const result = deriveExhibitSummary(
      fact({ source_tool: "get_linked_entities", value: { linked_customers: [], linked_accounts: [] } }),
    );
    expect(result?.conclusion).toBe("No supporting linked-entity relationship found");
  });

  it("linked entities: relationship found when a linked customer exists", () => {
    const result = deriveExhibitSummary(
      fact({ source_tool: "get_linked_entities", value: { linked_customers: ["cust_2"], linked_accounts: [] } }),
    );
    expect(result?.conclusion).toBe("Linked-entity relationship found");
    expect(result?.keyValue).toContain("1");
  });

  it("merchant risk: LOW/MEDIUM/HIGH map to the exact requested wording", () => {
    expect(deriveExhibitSummary(fact({ source_tool: "get_merchant_risk", value: { risk_band: "LOW" } }))?.conclusion).toBe(
      "Merchant risk profile is clean",
    );
    expect(deriveExhibitSummary(fact({ source_tool: "get_merchant_risk", value: { risk_band: "MEDIUM" } }))?.conclusion).toBe(
      "Merchant has moderate risk evidence",
    );
    expect(deriveExhibitSummary(fact({ source_tool: "get_merchant_risk", value: { risk_band: "HIGH" } }))?.conclusion).toBe(
      "Merchant has elevated risk evidence",
    );
  });

  it("kyc status: verified/review/failed", () => {
    expect(deriveExhibitSummary(fact({ source_tool: "get_mock_kyc_status", value: { kyc_status: "VERIFIED" } }))?.conclusion).toBe(
      "KYC verified",
    );
    expect(deriveExhibitSummary(fact({ source_tool: "get_mock_kyc_status", value: { kyc_status: "REVIEW" } }))?.conclusion).toBe(
      "KYC under review",
    );
  });

  it("returns null (safe fallback) for an unrecognized tool", () => {
    expect(deriveExhibitSummary(fact({ source_tool: "some_future_tool", value: { anything: 1 } }))).toBeNull();
  });

  it("returns null (safe fallback) when expected fields are missing, rather than fabricating a conclusion", () => {
    expect(deriveExhibitSummary(fact({ source_tool: "get_device_history", value: {} }))).toBeNull();
    expect(deriveExhibitSummary(fact({ source_tool: "get_merchant_risk", value: { risk_band: "unexpected" } }))).toBeNull();
  });
});
