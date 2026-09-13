# Sentinel

## Real-Time AI Fraud Investigation & Case Intelligence

Sentinel is an AI-assisted fraud investigation system for outgoing card-not-present (CNP) e-commerce transactions at the pre-authorization stage. It combines deterministic anomaly detection, an agentic evidence-gathering workflow, Gemini-based structured reasoning, decision robustness analysis, and a deterministic policy service to investigate suspicious transactions while keeping automated financial decisions governed by explicit policy and human oversight.

## V1 Architecture

```text
Transaction
    ↓
Detection
    ↓
Evidence Agent
    ↓
Gemini Reasoning
    ↓
Decision Robustness
    ↓
Deterministic Policy
    ↓
AUTO_RESOLVE / ESCALATE
    ↓
Firestore
    ↓
Analyst UI