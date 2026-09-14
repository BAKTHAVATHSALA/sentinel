"""Minimum-evidence floor for Sentinel V1 (Contracts v1.2 S7 / S11.4).

The floor is a deterministic table, not a prompt instruction: the Evidence
Agent cannot mark an evidence bundle COMPLETE until every tool its case's
anomaly tags require has actually been called, regardless of what the model
itself believes is sufficient.
"""

from __future__ import annotations

from shared.contracts.detection import AnomalyTag

MINIMUM_EVIDENCE_FLOOR: dict[AnomalyTag, tuple[str, ...]] = {
    AnomalyTag.NEW_DEVICE: ("get_device_history",),
    AnomalyTag.UNUSUAL_LOCATION: ("get_ip_geovelocity",),
    AnomalyTag.MERCHANT_RISK: ("get_merchant_risk",),
    AnomalyTag.UNUSUAL_AMOUNT: ("get_behavioral_baseline",),
    AnomalyTag.LINKED_ENTITY_ANOMALY: ("get_linked_entities",),
    AnomalyTag.KYC_ANOMALY: ("get_mock_kyc_status",),
}


def required_tools_for_tags(anomaly_tags: list[AnomalyTag]) -> list[str]:
    """Compute the minimum-evidence floor for a case as the union of each tag's requirement.

    :param anomaly_tags: Anomaly tags produced by Detection for this case.
    :return: Sorted, de-duplicated list of required tool names.
    """
    required: set[str] = set()
    for tag in anomaly_tags:
        required.update(MINIMUM_EVIDENCE_FLOOR.get(tag, ()))
    return sorted(required)


def is_floor_satisfied(tools_called: list[str], required_tools: list[str]) -> bool:
    """Check whether every required tool has actually been called.

    :param tools_called: Tool names actually called during the investigation.
    :param required_tools: Tools required by the case's minimum-evidence floor.
    :return: True only if every required tool appears in tools_called.
    """
    called = set(tools_called)
    return all(tool in called for tool in required_tools)


def missing_required_tools(tools_called: list[str], required_tools: list[str]) -> list[str]:
    """List required tools that have not yet been called, in floor order.

    :param tools_called: Tool names actually called during the investigation.
    :param required_tools: Tools required by the case's minimum-evidence floor.
    :return: Required tools not present in tools_called.
    """
    called = set(tools_called)
    return [tool for tool in required_tools if tool not in called]
