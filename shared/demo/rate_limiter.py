"""Hierarchical rate limiting and expensive operation guards for Sentinel Demo Mode.

Protects against:
1. Public endpoint scraping and flooding (Global and Per-IP limits).
2. Expensive Vertex AI Gemini quota exhaustion (Strict Counterfactual budget).
3. Concurrent reset races and rapid reset spam (Per-session budget and debounce).
4. Multiple parallel counterfactuals within the same session (In-flight locking).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import threading
import time

from fastapi import HTTPException


@dataclass
class SlidingWindowBucket:
    """Sliding-window timestamp tracker for a single limit key."""

    timestamps: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def check_and_record(self, max_allowed: int, window_seconds: float) -> tuple[bool, int]:
        """Check if request is allowed under the sliding window, and record if so.

        :param max_allowed: Maximum allowed requests within `window_seconds`.
        :param window_seconds: Sliding window duration in seconds.
        :return: (is_allowed, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - window_seconds
        with self.lock:
            # Evict expired entries
            self.timestamps = [t for t in self.timestamps if t > cutoff]
            if len(self.timestamps) >= max_allowed:
                oldest = self.timestamps[0]
                retry_after = max(1, int(oldest + window_seconds - now))
                return False, retry_after

            self.timestamps.append(now)
            return True, 0


class DemoRateLimiter:
    """Thread-safe hierarchical rate limiter for Sentinel Demo Mode."""

    def __init__(self) -> None:
        self._buckets: dict[str, SlidingWindowBucket] = defaultdict(SlidingWindowBucket)
        self._in_flight_counterfactuals: set[str] = set()
        self._in_flight_lock = threading.Lock()
        self._last_reset_time: dict[str, float] = {}

    def reset_state(self) -> None:
        """Clear all rate limiting state (used for testing)."""
        self._buckets.clear()
        with self._in_flight_lock:
            self._in_flight_counterfactuals.clear()
        self._last_reset_time.clear()

    def check_global_limit(self, max_req: int = 300, window_sec: float = 60.0) -> None:
        """Enforce global traffic limit across all demo requests."""
        bucket = self._buckets["global_demo_traffic"]
        allowed, retry_after = bucket.check_and_record(max_req, window_sec)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Global demo capacity reached. Please wait before retrying.",
                headers={"Retry-After": str(retry_after)},
            )

    def check_ip_limit(self, client_ip: str, max_req: int = 60, window_sec: float = 60.0) -> None:
        """Enforce per-IP request limit for general demo traffic."""
        bucket = self._buckets[f"ip_general:{client_ip}"]
        allowed, retry_after = bucket.check_and_record(max_req, window_sec)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many demo requests from this IP. Please wait.",
                headers={"Retry-After": str(retry_after)},
            )

    def check_session_creation_limit(self, client_ip: str, max_sessions: int = 10, window_sec: float = 3600.0) -> None:
        """Limit session creation per IP."""
        bucket = self._buckets[f"ip_session_create:{client_ip}"]
        allowed, retry_after = bucket.check_and_record(max_sessions, window_sec)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Demo session creation limit exceeded for this IP. Please wait before creating another session.",
                headers={"Retry-After": str(retry_after)},
            )

    def check_counterfactual_limit(
        self, session_id: str, client_ip: str, max_session: int = 5, window_sec: float = 600.0
    ) -> None:
        """Guard expensive Gemini counterfactual calls."""
        # 1. Per-IP check: max 20 per hour
        ip_bucket = self._buckets[f"ip_counterfactual:{client_ip}"]
        ip_allowed, ip_retry = ip_bucket.check_and_record(20, 3600.0)
        if not ip_allowed:
            raise HTTPException(
                status_code=429,
                detail="Counterfactual simulation limit exceeded for this IP. Quota refreshes hourly.",
                headers={"Retry-After": str(ip_retry)},
            )

        # 2. Per-session check: max 5 per 10 minutes
        session_bucket = self._buckets[f"session_counterfactual:{session_id}"]
        allowed, retry_after = session_bucket.check_and_record(max_session, window_sec)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Demo counterfactual simulation limit reached (max 5 per 10 minutes). Please wait.",
                headers={"Retry-After": str(retry_after)},
            )

    def acquire_counterfactual_in_flight(self, session_id: str) -> None:
        """Ensure at most one concurrent counterfactual per session."""
        with self._in_flight_lock:
            if session_id in self._in_flight_counterfactuals:
                raise HTTPException(
                    status_code=409,
                    detail="A counterfactual simulation is already in progress for this session. Please wait for it to complete.",
                )
            self._in_flight_counterfactuals.add(session_id)

    def release_counterfactual_in_flight(self, session_id: str) -> None:
        """Release the concurrent counterfactual lock."""
        with self._in_flight_lock:
            self._in_flight_counterfactuals.discard(session_id)

    def check_reset_limit(
        self, session_id: str, client_ip: str, max_resets: int = 3, window_sec: float = 600.0, debounce_sec: float = 10.0
    ) -> None:
        """Guard reset operations with debounce and rate limits."""
        now = time.time()
        last = self._last_reset_time.get(session_id, 0.0)
        if now - last < debounce_sec:
            retry_after = max(1, int(debounce_sec - (now - last)))
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {retry_after}s before resetting the demo again.",
                headers={"Retry-After": str(retry_after)},
            )

        # Per-IP check: max 10 resets per hour
        ip_bucket = self._buckets[f"ip_reset:{client_ip}"]
        ip_allowed, ip_retry = ip_bucket.check_and_record(10, 3600.0)
        if not ip_allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many demo resets from this IP. Please wait.",
                headers={"Retry-After": str(ip_retry)},
            )

        # Per-session check: max 3 per 10 minutes
        session_bucket = self._buckets[f"session_reset:{session_id}"]
        allowed, retry_after = session_bucket.check_and_record(max_resets, window_sec)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Demo reset limit reached (max 3 per 10 minutes).",
                headers={"Retry-After": str(retry_after)},
            )

        self._last_reset_time[session_id] = now


# Global singleton instance
demo_rate_limiter = DemoRateLimiter()
