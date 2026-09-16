"""Live Firestore tests for shared/auth/assignment.py's round-robin pointer,
against the real `sentinel-ai-builder-cup` project -- same real-infrastructure
pattern as tests/persistence/test_case_store_live.py. Each test uses its own
disposable pointer document (via a dedicated AssignmentStore/collection
instance is not configurable, so tests use disjoint, disposable uid sets that
don't depend on the pointer's prior state) to stay independent of run order."""

from __future__ import annotations

import uuid

import pytest

from shared.auth.assignment import AssignmentStore
from shared.persistence.firestore_client import build_firestore_client


@pytest.fixture()
def store() -> AssignmentStore:
    return AssignmentStore(build_firestore_client())


def test_zero_active_analysts_returns_none(store: AssignmentStore) -> None:
    assert store.assign_next_analyst([]) is None


def test_round_robin_cycles_through_a_disposable_uid_set(store: AssignmentStore) -> None:
    # A unique-per-run uid pair means whatever the shared pointer's prior
    # state was, neither uid can already equal it -- the first call always
    # starts at index 0 deterministically.
    uid_a, uid_b = f"rr_test_a_{uuid.uuid4().hex[:8]}", f"rr_test_b_{uuid.uuid4().hex[:8]}"
    pool = sorted([uid_a, uid_b])

    first = store.assign_next_analyst(pool)
    second = store.assign_next_analyst(pool)
    third = store.assign_next_analyst(pool)

    assert first == pool[0]
    assert second == pool[1]
    assert third == pool[0]  # wrapped around


def test_pool_shrinking_still_returns_a_member_of_the_new_pool(store: AssignmentStore) -> None:
    uid_a, uid_b, uid_c = (f"rr_shrink_{c}_{uuid.uuid4().hex[:8]}" for c in "abc")
    full_pool = sorted([uid_a, uid_b, uid_c])

    store.assign_next_analyst(full_pool)
    shrunk_pool = sorted([uid_a, uid_c])  # uid_b went inactive

    result = store.assign_next_analyst(shrunk_pool)

    assert result in shrunk_pool
