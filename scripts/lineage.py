"""Shared file-lineage hashing for the offline ML scripts (train/evaluate/split).

Every script that touches a dataset or model artifact records its SHA-256 so
a later run (or a reviewer) can confirm exactly which file version produced
a given result -- this was independently duplicated identically in three
scripts before being extracted here.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_file_sha256(filepath: Path) -> str:
    """Compute the SHA-256 hex digest of a file for lineage tracking."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()
