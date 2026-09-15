"""Real Firestore client for Sentinel V1 (Contracts V1-Scoped S24/S25).

Authentication is Application Default Credentials only -- no API key is
read or stored here, matching shared/evidence/gemini_client.py and
shared/reasoning/gemini_client.py's pattern. The service account,
`sentinel-v1-sa`, is least-privilege (Vertex AI User + Firestore User),
never Owner/Editor.
"""

from __future__ import annotations

from google.cloud import firestore

from shared.config import get_firestore_database, get_gcp_project_id


def build_firestore_client() -> firestore.Client:
    """Construct a real Firestore client for the configured project/database.

    :return: A google.cloud.firestore.Client using Application Default Credentials.
    """
    return firestore.Client(project=get_gcp_project_id(), database=get_firestore_database())
