"""Gemini function-calling declarations for the six Sentinel V1 evidence tools.

These are the schemas Gemini actually sees (Contracts v1.2 S11.3 "explicit
tool allow-list"). They are a practical subset of shared.contracts.tools'
frozen Input models where a full nested object would be unwieldy as a
function-call argument (see get_behavioral_baseline) -- shared.evidence.tools
hydrates whatever Gemini supplies back into the true contract shape before
validation.
"""

from __future__ import annotations

from google.genai import types

from shared.evidence.tools import TOOL_REGISTRY

_GEO_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "lat": {"type": "STRING"},
        "lon": {"type": "STRING"},
        "country": {"type": "STRING"},
    },
    "required": ["lat", "lon", "country"],
}

TOOL_PARAMETER_SCHEMAS: dict[str, dict[str, object]] = {
    "get_device_history": {
        "type": "OBJECT",
        "properties": {
            "customer_id": {"type": "STRING"},
            "device_id": {"type": "STRING"},
        },
        "required": ["customer_id", "device_id"],
    },
    "get_ip_geovelocity": {
        "type": "OBJECT",
        "properties": {
            "customer_id": {"type": "STRING"},
            "current_ip": {"type": "STRING"},
            "current_geo": _GEO_SCHEMA,
            "transaction_timestamp": {"type": "STRING", "description": "ISO-8601 timestamp"},
        },
        "required": ["customer_id", "current_ip", "current_geo", "transaction_timestamp"],
    },
    "get_behavioral_baseline": {
        "type": "OBJECT",
        "properties": {
            "customer_id": {"type": "STRING"},
            "transaction_id": {"type": "STRING", "description": "The transaction_id under investigation"},
        },
        "required": ["customer_id", "transaction_id"],
    },
    "get_linked_entities": {
        "type": "OBJECT",
        "properties": {
            "customer_id": {"type": "STRING"},
            "account_id": {"type": "STRING", "description": "Account identifier to check for linkage"},
        },
        "required": ["customer_id", "account_id"],
    },
    "get_merchant_risk": {
        "type": "OBJECT",
        "properties": {
            "merchant_id": {"type": "STRING"},
            "customer_id": {"type": "STRING"},
        },
        "required": ["merchant_id", "customer_id"],
    },
    "get_mock_kyc_status": {
        "type": "OBJECT",
        "properties": {"customer_id": {"type": "STRING"}},
        "required": ["customer_id"],
    },
}

# Explicit six-tool allow-list, in a stable order -- Contracts v1.2 S11.3.
EVIDENCE_TOOL_NAMES: tuple[str, ...] = (
    "get_device_history",
    "get_ip_geovelocity",
    "get_behavioral_baseline",
    "get_linked_entities",
    "get_merchant_risk",
    "get_mock_kyc_status",
)


def build_evidence_tool() -> types.Tool:
    """Build the single Gemini Tool exposing exactly the six allow-listed evidence functions."""
    declarations = [
        types.FunctionDeclaration(
            name=name,
            description=TOOL_REGISTRY[name].description,
            parameters=TOOL_PARAMETER_SCHEMAS[name],
        )
        for name in EVIDENCE_TOOL_NAMES
    ]
    return types.Tool(function_declarations=declarations)
