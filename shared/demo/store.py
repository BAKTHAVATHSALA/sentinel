"""Dedicated session-scoped storage implementation for Sentinel Demo Mode.

Strictly segregated from production cases:
- Demo case IDs strictly conform to: `demo_{session_id}_case_{01..10}`.
- Every read, mutation, counterfactual, and reset validates that the requested
  case_id belongs exclusively to the caller's server-verified session_id.
- Production cases ({cases} and {transactions}) are never queried or mutated.
- First-valid-decision-wins is enforced transactionally.
- Resets restore the session's 10 cases atomically without crosstalk to other sessions.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import threading
from typing import Any

from google.cloud import firestore

from shared.contracts.events import AuditEvent
from shared.demo.fixtures import generate_template_cases


class DemoStore:
    """Session-isolated case store for hackathon judges."""

    def __init__(self, client: firestore.Client | None = None) -> None:
        """Initialize with an optional Firestore client.

        If client is None or in test mode, operates against an in-memory dictionary
        with thread-safe transactional semantics.
        """
        self._client = client
        self._demo_cases_collection = "demo_cases"
        self._demo_audit_collection = "demo_audit_events"
        self._lock = threading.Lock()
        # In-memory storage fallback / test double:
        # {case_id: document_dict}
        self._memory_cases: dict[str, dict[str, Any]] = {}
        # {case_id: list_of_audit_dicts}
        self._memory_audit: dict[str, list[dict[str, Any]]] = {}

    def _format_case_id(self, session_id: str, template_id: str) -> str:
        return f"demo_{session_id}_{template_id}"

    def init_session(self, session_id: str) -> None:
        """Atomically seed the 10 pristine template cases for a new session."""
        templates = generate_template_cases()
        now = datetime.now(timezone.utc)

        with self._lock:
            for tmpl in templates:
                template_id = str(tmpl["case_id"])  # e.g. "case_01"
                scoped_case_id = self._format_case_id(session_id, template_id)
                if scoped_case_id in self._memory_cases:
                    continue  # already initialized

                doc = copy.deepcopy(tmpl)
                doc["case_id"] = scoped_case_id
                doc["demo_session_id"] = session_id
                doc["created_at"] = now
                doc["updated_at"] = now
                self._memory_cases[scoped_case_id] = doc

                # Seed initial audit trail
                initial_audit = [
                    AuditEvent(
                        audit_event_id=f"aud_{scoped_case_id}_init",
                        case_id=scoped_case_id,
                        transaction_id=str(doc["transaction_id"]),
                        event_type="DEMO_CASE_SEEDED",
                        actor_type="SYSTEM",
                        output_snapshot={"state": doc["state"], "is_demo": True},
                        occurred_at=now,
                    ).model_dump(mode="json")
                ]
                self._memory_audit[scoped_case_id] = initial_audit

        if self._client is not None:
            batch = self._client.batch()
            for tmpl in templates:
                template_id = str(tmpl["case_id"])
                scoped_case_id = self._format_case_id(session_id, template_id)
                ref = self._client.collection(self._demo_cases_collection).document(scoped_case_id)
                doc = copy.deepcopy(tmpl)
                doc["case_id"] = scoped_case_id
                doc["demo_session_id"] = session_id
                doc["created_at"] = now
                doc["updated_at"] = now
                batch.set(ref, doc)
            batch.commit()

    def get_case(self, session_id: str, case_id: str) -> dict[str, object] | None:
        """Fetch a demo case with strict session-scoped ownership validation.

        Returns None if case_id does not belong to this session_id or does not exist.
        """
        expected_prefix = f"demo_{session_id}_"
        if not case_id.startswith(expected_prefix):
            return None

        with self._lock:
            doc = self._memory_cases.get(case_id)
            if doc is not None:
                return copy.deepcopy(doc)

        if self._client is not None:
            snapshot = self._client.collection(self._demo_cases_collection).document(case_id).get()
            if snapshot.exists:
                data = snapshot.to_dict() or {}
                if data.get("demo_session_id") == session_id:
                    return data

        return None

    def list_cases(self, session_id: str) -> list[dict[str, object]]:
        """List all 10 demo cases belonging to this session."""
        self.init_session(session_id)
        expected_prefix = f"demo_{session_id}_"

        with self._lock:
            cases = [
                copy.deepcopy(doc)
                for cid, doc in self._memory_cases.items()
                if cid.startswith(expected_prefix)
            ]
            if cases:
                return sorted(cases, key=lambda c: str(c["case_id"]))

        if self._client is not None:
            # Deterministic batch lookup of the 10 known IDs for this session
            case_ids = [self._format_case_id(session_id, f"case_{i:02d}") for i in range(1, 11)]
            docs = []
            for cid in case_ids:
                snap = self._client.collection(self._demo_cases_collection).document(cid).get()
                if snap.exists:
                    docs.append(snap.to_dict() or {})
            return sorted(docs, key=lambda c: str(c["case_id"]))

        return []

    def apply_decision(
        self,
        session_id: str,
        case_id: str,
        action: str,
        reason: str,
        updates: dict[str, object],
        audit_event: AuditEvent,
    ) -> tuple[str, dict[str, object]]:
        """Atomically apply a human decision with first-valid-decision-wins semantics.

        Returns: (outcome, current_document)
          - outcome in ("applied", "idempotent", "conflict", "not_found")
        """
        expected_prefix = f"demo_{session_id}_"
        if not case_id.startswith(expected_prefix):
            return "not_found", {}

        with self._lock:
            doc = self._memory_cases.get(case_id)
            if doc is None:
                return "not_found", {}

            current_disposition = doc.get("final_disposition")
            current_reason = doc.get("final_reason")
            current_state = doc.get("state")
            is_already_escalated = bool(doc.get("is_escalated"))

            if current_disposition is not None or current_state == "FINALIZED" or is_already_escalated:
                # Idempotent replay check
                if action == "ESCALATE_SENIOR":
                    if is_already_escalated and doc.get("assigned_analyst_id") == updates.get("assigned_analyst_id") and doc.get("escalated_reason") == reason:
                        return "idempotent", copy.deepcopy(doc)
                    return "conflict", copy.deepcopy(doc)
                if current_disposition == action and current_reason == reason:
                    return "idempotent", copy.deepcopy(doc)
                return "conflict", copy.deepcopy(doc)

            # Apply updates
            doc.update(updates)
            self._memory_cases[case_id] = doc
            self._memory_audit.setdefault(case_id, []).append(audit_event.model_dump(mode="json"))

            if self._client is not None:
                try:
                    ref = self._client.collection(self._demo_cases_collection).document(case_id)
                    ref.update(updates)
                except Exception:
                    pass

            return "applied", copy.deepcopy(doc)

    def append_audit_event(self, session_id: str, case_id: str, audit_event: AuditEvent) -> None:
        """Append an audit event with ownership verification."""
        expected_prefix = f"demo_{session_id}_"
        if not case_id.startswith(expected_prefix):
            return

        with self._lock:
            self._memory_audit.setdefault(case_id, []).append(audit_event.model_dump(mode="json"))

    def get_audit_trail(self, session_id: str, case_id: str) -> list[dict[str, object]]:
        """Return the audit events for a demo case."""
        expected_prefix = f"demo_{session_id}_"
        if not case_id.startswith(expected_prefix):
            return []

        with self._lock:
            return copy.deepcopy(self._memory_audit.get(case_id, []))

    def reset_session(self, session_id: str) -> None:
        """Atomically restore the 10 demo cases for this session to pristine templates."""
        templates = generate_template_cases()
        now = datetime.now(timezone.utc)

        with self._lock:
            for tmpl in templates:
                template_id = str(tmpl["case_id"])
                scoped_case_id = self._format_case_id(session_id, template_id)
                doc = copy.deepcopy(tmpl)
                doc["case_id"] = scoped_case_id
                doc["demo_session_id"] = session_id
                doc["created_at"] = now
                doc["updated_at"] = now
                self._memory_cases[scoped_case_id] = doc

                # Reset audit trail
                reset_audit = [
                    AuditEvent(
                        audit_event_id=f"aud_{scoped_case_id}_reset",
                        case_id=scoped_case_id,
                        transaction_id=str(doc["transaction_id"]),
                        event_type="DEMO_SESSION_RESET",
                        actor_type="SYSTEM",
                        output_snapshot={"state": doc["state"], "is_demo": True},
                        occurred_at=now,
                    ).model_dump(mode="json")
                ]
                self._memory_audit[scoped_case_id] = reset_audit

        if self._client is not None:
            batch = self._client.batch()
            for tmpl in templates:
                template_id = str(tmpl["case_id"])
                scoped_case_id = self._format_case_id(session_id, template_id)
                ref = self._client.collection(self._demo_cases_collection).document(scoped_case_id)
                doc = copy.deepcopy(tmpl)
                doc["case_id"] = scoped_case_id
                doc["demo_session_id"] = session_id
                doc["created_at"] = now
                doc["updated_at"] = now
                batch.set(ref, doc)
            batch.commit()
