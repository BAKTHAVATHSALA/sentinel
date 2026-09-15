"""HARD_RISK_TAGS -- the named constant resolving Policy Rule P-004's
auto-resolve ambiguity (Contracts V1-Scoped S6.3, S16 Rule P-004).

Anomaly tags split into two categories, based on whether the signal is
something `risk_score` structurally can already see:

- Statistical tags (NEW_DEVICE, UNUSUAL_LOCATION, UNUSUAL_AMOUNT) are
  deviations from the customer's own baseline -- exactly the kind of
  feature `risk_score` is trained on, so they are not hard tags.
- Structural tags (HARD_RISK_TAGS below) are evidence about something a
  single per-transaction score cannot see by construction: a third party's
  risk profile, or cross-account correlation. These get a categorical veto
  over auto-resolve, regardless of risk_score (Safety Invariant 6).

This is the single source of truth for that veto set. Contracts V1-Scoped
S6.3 requires it be referenced by name, never reimplemented as an inline
literal, so Policy Rule P-004 (shared/policy/rules.py) imports this exact
constant rather than restating the tag list.
"""

from __future__ import annotations

from shared.contracts.detection import AnomalyTag

HARD_RISK_TAGS: tuple[AnomalyTag, ...] = (
    AnomalyTag.MERCHANT_RISK,
    AnomalyTag.LINKED_ENTITY_ANOMALY,
    AnomalyTag.KYC_ANOMALY,
)
