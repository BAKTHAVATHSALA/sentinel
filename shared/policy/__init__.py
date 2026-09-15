"""Deterministic Policy package for Sentinel V1 (Contracts V1-Scoped S15/S16,
Build Checklist Phase 4.1): the sole automated disposition authority.

Policy may only ever produce AUTO_RESOLVE or ESCALATE -- never BLOCK_HOLD.
Only the human decision path (Contracts V1-Scoped S18) may execute
BLOCK_HOLD."""
