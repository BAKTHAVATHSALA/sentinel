import type { Fact } from "./types";

/**
 * Deterministic, per-tool concise conclusions for a collapsed evidence
 * exhibit -- derived exclusively from the real fields each evidence tool
 * contract returns (shared/contracts/tools.py), never invented. The exact
 * field names and comparison thresholds here mirror what the tools
 * themselves and Detection's own rules already compare against (e.g. the
 * 800km location-deviation threshold in shared/detection/rules.py) purely
 * for a presentational label -- this never redefines or duplicates any
 * detection/policy decision, it only describes the same real numbers.
 *
 * If a fact's `source_tool` isn't recognized, or its expected fields are
 * missing/malformed, this returns null and the caller falls back to the
 * exhibit's existing title/key-value display rather than guessing.
 */

const LOCATION_DEVIATION_THRESHOLD_KM = 800;
const AMOUNT_DEVIATION_CONSISTENT_THRESHOLD = 2;

export interface ExhibitSummary {
  conclusion: string;
  keyValue?: string;
}

export function deriveExhibitSummary(fact: Fact): ExhibitSummary | null {
  const v = fact.value;

  switch (fact.source_tool) {
    case "get_device_history": {
      if (typeof v.known_device !== "boolean") return null;
      return {
        conclusion: v.known_device ? "Known device confirmed" : "New device confirmed",
        keyValue: typeof v.transaction_count === "number" ? `${v.transaction_count} prior transactions` : undefined,
      };
    }

    case "get_ip_geovelocity": {
      const distance = typeof v.distance_km === "string" ? parseFloat(v.distance_km) : Number(v.distance_km);
      if (Number.isNaN(distance)) return null;
      if (v.impossible_travel === true) {
        return { conclusion: "Impossible travel detected", keyValue: `${distance.toFixed(0)} km` };
      }
      return {
        conclusion:
          distance > LOCATION_DEVIATION_THRESHOLD_KM
            ? "Location differs from customer baseline"
            : "Location consistent with customer baseline",
        keyValue: `${distance.toFixed(0)} km from last known location`,
      };
    }

    case "get_behavioral_baseline": {
      const deviation =
        typeof v.amount_deviation === "string" ? parseFloat(v.amount_deviation) : Number(v.amount_deviation);
      if (Number.isNaN(deviation)) return null;
      return {
        conclusion:
          deviation <= AMOUNT_DEVIATION_CONSISTENT_THRESHOLD
            ? "Amount consistent with customer behavior"
            : "Amount deviates from customer behavior",
        keyValue: typeof v.typical_amount === "string" ? `typical ~$${parseFloat(v.typical_amount).toFixed(0)}` : undefined,
      };
    }

    case "get_linked_entities": {
      const linkedCustomers = Array.isArray(v.linked_customers) ? v.linked_customers : null;
      const linkedAccounts = Array.isArray(v.linked_accounts) ? v.linked_accounts : null;
      if (linkedCustomers === null || linkedAccounts === null) return null;
      const total = linkedCustomers.length + linkedAccounts.length;
      return {
        conclusion: total === 0 ? "No supporting linked-entity relationship found" : "Linked-entity relationship found",
        keyValue: total > 0 ? `${total} linked ${total === 1 ? "entity" : "entities"}` : undefined,
      };
    }

    case "get_merchant_risk": {
      const band = v.risk_band;
      if (band !== "LOW" && band !== "MEDIUM" && band !== "HIGH") return null;
      const conclusion =
        band === "LOW"
          ? "Merchant risk profile is clean"
          : band === "MEDIUM"
            ? "Merchant has moderate risk evidence"
            : "Merchant has elevated risk evidence";
      return {
        conclusion,
        keyValue: typeof v.recent_fraud_report_count === "number" ? `${v.recent_fraud_report_count} recent fraud reports` : undefined,
      };
    }

    case "get_mock_kyc_status": {
      const status = v.kyc_status;
      if (status !== "VERIFIED" && status !== "REVIEW" && status !== "FAILED") return null;
      const conclusion =
        status === "VERIFIED" ? "KYC verified" : status === "REVIEW" ? "KYC under review" : "KYC verification failed";
      const flags = Array.isArray(v.kyc_flags) ? v.kyc_flags : [];
      return { conclusion, keyValue: flags.length > 0 ? `${flags.length} flag${flags.length === 1 ? "" : "s"}` : undefined };
    }

    default:
      return null;
  }
}
