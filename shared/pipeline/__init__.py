"""Full pipeline wiring for Sentinel V1 (Contracts V1-Scoped S19, Build
Checklist Phase 4.3): Detection -> (if flagged) Evidence Agent -> Reasoning
-> Robustness Scorer -> Policy -> Firestore write, all in-process within one
Cloud Run service."""
