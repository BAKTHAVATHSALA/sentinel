"""Centralized environment configuration for Sentinel V1.

Loads GCP/Gemini settings from the process environment (populated from a
local .env via python-dotenv when present). No secrets live here -- Google
Cloud auth is via Application Default Credentials, never an API key.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_GCP_PROJECT_ID = "sentinel-ai-builder-cup"
DEFAULT_GCP_REGION = "us-central1"
DEFAULT_GEMINI_AGENT_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_REASONING_MODEL = "gemini-2.5-pro"


def get_gcp_project_id() -> str:
    """Return the configured GCP project ID for Vertex AI calls."""
    return os.getenv("GCP_PROJECT_ID") or DEFAULT_GCP_PROJECT_ID


def get_gcp_region() -> str:
    """Return the configured GCP region for Vertex AI calls."""
    return os.getenv("GCP_REGION") or DEFAULT_GCP_REGION


def get_gemini_agent_model() -> str:
    """Return the Gemini model configured for the Evidence Agent.

    Gemini Flash is used here deliberately (not Pro) -- the Evidence Agent
    makes up to 6 bounded tool-selection calls per case, so latency and cost
    per call matter far more than the deeper reasoning Pro would add.
    Reasoning (Phase 3) uses Pro separately via a different setting.
    """
    return os.getenv("GEMINI_AGENT_MODEL") or DEFAULT_GEMINI_AGENT_MODEL


def get_gemini_reasoning_model() -> str:
    """Return the Gemini model configured for the Reasoning component.

    Gemini Pro is used here deliberately (not Flash) -- Reasoning makes one
    low-volume, high-stakes synthesis call per case (at most two, on a
    citation reprompt), so reasoning depth matters far more than per-call
    latency or cost. The Evidence Agent (Phase 2) uses Flash separately via
    a different setting.
    """
    return os.getenv("GEMINI_REASONING_MODEL") or DEFAULT_GEMINI_REASONING_MODEL
