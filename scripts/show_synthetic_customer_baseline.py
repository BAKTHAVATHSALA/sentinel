"""Read-only local reference tool: prints the deterministic synthetic
baseline Sentinel will compute for a given customer/merchant identity, so a
transaction document can be authored to genuinely match (or deliberately
deviate from) that baseline -- the same way a QA engineer would use a known
test account's real device list.

This is NOT an HTTP endpoint, NOT a backdoor, and NOT an alternate
investigation path. It calls the exact same pure functions
(shared/generator/synthesis.py) that POST /transactions itself uses
internally to resolve an unknown transaction's context. It never invokes
Detection, Evidence Agent, Reasoning, Robustness, or Policy, and it never
talks to Firestore, Vertex AI, or Gemini -- purely local, deterministic
computation, safe to run any number of times with no side effects.

Run:
    python -m scripts.show_synthetic_customer_baseline \\
        --customer-id cust_demo_001 --account-id acc_demo_001 --card-id card_demo_001 \\
        --merchant-id merch_demo_001
"""

from __future__ import annotations

import argparse
import json

from shared.generator.synthesis import derive_customer_baseline, derive_linked_entity, derive_merchant_profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--card-id", required=True)
    parser.add_argument("--merchant-id", default=None, help="Optional: also show this merchant's stable profile.")
    args = parser.parse_args()

    customer, known_devices = derive_customer_baseline(args.customer_id, args.account_id, args.card_id)
    secondary = derive_linked_entity(args.customer_id, args.account_id, args.card_id)

    print("=== CUSTOMER BASELINE (stable, derived only from customer_id/account_id/card_id) ===")
    print(
        json.dumps(
            {
                "customer_id": customer.customer_id,
                "account_id": customer.account_id,
                "card_id": customer.card_id,
                "known_device_ids": known_devices,
                "home_geo": {
                    "lat": str(customer.home_geo.lat),
                    "lon": str(customer.home_geo.lon),
                    "country": customer.home_geo.country,
                },
                "normal_amount_mean": str(customer.typical_amount_mean),
                "normal_amount_std": str(customer.typical_amount_std),
                "tenure_months": customer.tenure_months,
                "kyc_status": customer.kyc_status,
                "primary_ip": customer.primary_ip,
                "linked_entity_present": secondary is not None,
                "linked_entity_kyc_status": secondary.kyc_status if secondary else None,
            },
            indent=2,
        )
    )
    print(
        "\nA transaction using one of the known_device_ids above, a geo near home_geo, and an "
        "amount within normal_amount_mean +/- a few times normal_amount_std will be compared as "
        "'known device' / 'normal location' / 'normal amount' by the real Detection rules -- "
        "Detection still decides the actual anomaly tags; this only tells you what it will compare against."
    )

    if args.merchant_id:
        merchant = derive_merchant_profile(args.merchant_id)
        print("\n=== MERCHANT PROFILE (stable, derived only from merchant_id) ===")
        print(
            json.dumps(
                {
                    "merchant_id": merchant.merchant_id,
                    "category": merchant.category,
                    "risk_band": merchant.risk_band.value,
                    "chargeback_rate": str(merchant.chargeback_rate),
                    "fraud_report_trend": merchant.fraud_report_trend.value,
                    "recent_fraud_report_count": merchant.recent_fraud_report_count,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
