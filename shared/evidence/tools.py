"""Evidence tool layer for Sentinel V1: the six read-only, mocked tools the
Evidence Agent may call, each wrapped with input validation, a per-tool
timeout, and a structured error on failure (Contracts v1.2 S12).

Every successful call is normalized into a single Fact (S9) -- the only unit
the rest of the pipeline (Reasoning citations, the Robustness Scorer) ever
sees.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
import time

from pydantic import BaseModel, ValidationError

from shared.contracts.fact import Fact, FactQuality
from shared.contracts.tools import (
    BehavioralBaselineInput,
    BehavioralBaselineOutput,
    DeviceHistoryInput,
    DeviceHistoryOutput,
    IpGeovelocityInput,
    IpGeovelocityOutput,
    LinkedEntitiesInput,
    LinkedEntitiesOutput,
    MerchantRiskInput,
    MerchantRiskOutput,
    MockKycInput,
    MockKycOutput,
)
from shared.evidence.errors import (
    ToolError,
    ToolExecutionError,
    ToolTimeoutError,
    ToolValidationError,
    UnknownToolError,
)
from shared.evidence.fixtures import (
    FixtureContext,
    get_failing_tool,
    resolve_behavioral_baseline,
    resolve_device_history,
    resolve_ip_geovelocity,
    resolve_linked_entities,
    resolve_merchant_risk,
    resolve_mock_kyc_status,
)

# Per-tool wall-clock budget. All V1 tools read local fixture data, so this
# only matters for the deliberately-forced-failure scenario proving the
# fail-safe escalation path (Contracts v1.2 S14).
TOOL_TIMEOUT_SECONDS = 3.0

TOOL_FACT_TYPE: dict[str, str] = {
    "get_device_history": "DEVICE_HISTORY",
    "get_ip_geovelocity": "IP_GEOVELOCITY",
    "get_behavioral_baseline": "BEHAVIORAL_BASELINE",
    "get_linked_entities": "LINKED_ENTITIES",
    "get_merchant_risk": "MERCHANT_RISK",
    "get_mock_kyc_status": "KYC_STATUS",
}


@dataclass(frozen=True)
class ToolSpec:
    """Registration record for one evidence tool: contract shapes + resolver + description."""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    resolver: Callable[..., dict[str, object]]
    subject_field: str


def _resolve_device_history(ctx: FixtureContext, validated: DeviceHistoryInput) -> dict[str, object]:
    return resolve_device_history(ctx, validated.customer_id, validated.device_id)


def _resolve_ip_geovelocity(ctx: FixtureContext, validated: IpGeovelocityInput) -> dict[str, object]:
    from shared.contracts.transaction import Geo

    geo = Geo.model_validate(validated.current_geo)
    return resolve_ip_geovelocity(
        ctx, validated.customer_id, validated.current_ip, geo, validated.transaction_timestamp
    )


def _resolve_behavioral_baseline(ctx: FixtureContext, validated: BehavioralBaselineInput) -> dict[str, object]:
    return resolve_behavioral_baseline(ctx, validated.customer_id, ctx.transaction)


def _resolve_linked_entities(ctx: FixtureContext, validated: LinkedEntitiesInput) -> dict[str, object]:
    return resolve_linked_entities(ctx, validated.customer_id, validated.account_id)


def _resolve_merchant_risk(ctx: FixtureContext, validated: MerchantRiskInput) -> dict[str, object]:
    return resolve_merchant_risk(ctx, validated.merchant_id, validated.customer_id)


def _resolve_mock_kyc_status(ctx: FixtureContext, validated: MockKycInput) -> dict[str, object]:
    return resolve_mock_kyc_status(ctx, validated.customer_id)


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "get_device_history": ToolSpec(
        name="get_device_history",
        description=(
            "Look up the history of a device for a customer: whether it is a known "
            "device, when it was first/last seen, how many transactions it has, and "
            "any risk signals (e.g. seen on a different account recently)."
        ),
        input_model=DeviceHistoryInput,
        output_model=DeviceHistoryOutput,
        resolver=_resolve_device_history,
        subject_field="device_id",
    ),
    "get_ip_geovelocity": ToolSpec(
        name="get_ip_geovelocity",
        description=(
            "Compare the transaction's IP/geo location against the customer's most "
            "recent known location to compute distance, elapsed time, and whether the "
            "implied travel speed is physically implausible."
        ),
        input_model=IpGeovelocityInput,
        output_model=IpGeovelocityOutput,
        resolver=_resolve_ip_geovelocity,
        subject_field="customer_id",
    ),
    "get_behavioral_baseline": ToolSpec(
        name="get_behavioral_baseline",
        description=(
            "Compare the transaction amount and time-of-day against the customer's "
            "established spending baseline, returning deviation measures."
        ),
        input_model=BehavioralBaselineInput,
        output_model=BehavioralBaselineOutput,
        resolver=_resolve_behavioral_baseline,
        subject_field="customer_id",
    ),
    "get_linked_entities": ToolSpec(
        name="get_linked_entities",
        description=(
            "Given a customer and an account, discover linked customers/accounts and "
            "any relationship or recent-anomaly signals connecting them -- use this to "
            "follow up when another tool reveals a relationship worth investigating."
        ),
        input_model=LinkedEntitiesInput,
        output_model=LinkedEntitiesOutput,
        resolver=_resolve_linked_entities,
        subject_field="account_id",
    ),
    "get_merchant_risk": ToolSpec(
        name="get_merchant_risk",
        description=(
            "Look up merchant risk evidence: category, onboarding date, chargeback "
            "rate, recent fraud-report count and trend, and how many prior "
            "transactions this customer has with this merchant."
        ),
        input_model=MerchantRiskInput,
        output_model=MerchantRiskOutput,
        resolver=_resolve_merchant_risk,
        subject_field="merchant_id",
    ),
    "get_mock_kyc_status": ToolSpec(
        name="get_mock_kyc_status",
        description="Look up the customer's KYC verification status and any KYC flags.",
        input_model=MockKycInput,
        output_model=MockKycOutput,
        resolver=_resolve_mock_kyc_status,
        subject_field="customer_id",
    ),
}


def _hydrate_behavioral_baseline_args(raw_args: dict[str, Any], ctx: FixtureContext) -> dict[str, Any]:
    """Expand a transaction_id reference into the full Transaction the contract requires.

    Gemini is given a lightweight {customer_id, transaction_id} schema for this tool
    (a full nested Transaction object is unwieldy as a function-call argument, and V1
    ever investigates exactly one transaction per case) -- this hydrates that reference
    back into the BehavioralBaselineInput.transaction field before contract validation.
    """
    if "transaction" in raw_args:
        return raw_args
    transaction_id = raw_args.get("transaction_id")
    if transaction_id is not None and transaction_id != ctx.transaction.transaction_id:
        raise ToolValidationError(
            "get_behavioral_baseline",
            f"Unknown transaction_id '{transaction_id}' for this case",
        )
    return {"customer_id": raw_args.get("customer_id"), "transaction": ctx.transaction}


def _simulate_forced_failure(tool_name: str, ctx: FixtureContext) -> None:
    """Sleep or raise if this tool is the case's deliberately-forced failure.

    Runs *inside* the timeout-bounded worker so a forced TIMEOUT genuinely
    exhausts the per-tool budget rather than being special-cased.
    """
    failing = get_failing_tool(ctx)
    if not failing or failing.get("tool_name") != tool_name:
        return
    mode = failing.get("failure_mode")
    if mode == "TIMEOUT":
        time.sleep(TOOL_TIMEOUT_SECONDS + 1.0)
        return
    raise ToolExecutionError(tool_name, str(failing.get("reason", "Deliberately forced tool failure")))


def _run_bounded(tool_name: str, fn: Callable[[], dict[str, object]]) -> dict[str, object]:
    """Execute fn under the per-tool wall-clock timeout, raising structured errors only."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=TOOL_TIMEOUT_SECONDS)
        except FutureTimeoutError as exc:
            raise ToolTimeoutError(tool_name, f"Exceeded {TOOL_TIMEOUT_SECONDS}s timeout budget") from exc
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001 -- must never leak a raw/silent exception
            raise ToolExecutionError(tool_name, str(exc)) from exc


def call_tool(tool_name: str, raw_args: dict[str, Any], ctx: FixtureContext, call_index: int) -> Fact:
    """Validate, execute, and normalize one evidence tool call into a Fact.

    :param tool_name: Requested tool name; must be in the explicit six-tool allow-list.
    :param raw_args: Raw (Gemini-supplied) function-call arguments.
    :param ctx: Fixture context for the active investigation.
    :param call_index: 1-based position of this call within the investigation, for fact_id.
    :return: The normalized Fact for this tool call.
    :raises ToolError: on any allow-list, validation, timeout, or execution failure.
    """
    spec = TOOL_REGISTRY.get(tool_name)
    if spec is None:
        raise UnknownToolError(tool_name, "Tool is not in the six-tool allow-list")

    args = raw_args
    if tool_name == "get_behavioral_baseline":
        args = _hydrate_behavioral_baseline_args(raw_args, ctx)

    try:
        validated_input = spec.input_model.model_validate(args)
    except ValidationError as exc:
        raise ToolValidationError(tool_name, str(exc)) from exc

    def _execute() -> dict[str, object]:
        _simulate_forced_failure(tool_name, ctx)
        return spec.resolver(ctx, validated_input)

    raw_output = _run_bounded(tool_name, _execute)
    derived = bool(raw_output.pop("_derived", False))

    try:
        validated_output = spec.output_model.model_validate(raw_output)
    except ValidationError as exc:
        raise ToolExecutionError(tool_name, f"Resolver produced an invalid output shape: {exc}") from exc

    return _normalize_to_fact(spec, validated_input, validated_output, ctx, call_index, derived)


def _normalize_to_fact(
    spec: ToolSpec,
    validated_input: BaseModel,
    validated_output: BaseModel,
    ctx: FixtureContext,
    call_index: int,
    derived: bool,
) -> Fact:
    """Wrap one validated tool output into the single Fact shape the rest of the pipeline consumes."""
    source_record_ids = getattr(validated_output, "source_record_ids", [])
    subject_id = getattr(validated_input, spec.subject_field, ctx.customer.customer_id)

    return Fact(
        fact_id=f"fact_{ctx.case_id}_{call_index:02d}_{spec.name}",
        type=TOOL_FACT_TYPE[spec.name],
        subject_id=str(subject_id),
        value=validated_output.model_dump(mode="json"),
        source_tool=spec.name,
        source_record_id=source_record_ids[0] if source_record_ids else None,
        observed_at=ctx.transaction.timestamp,
        retrieved_at=datetime.now(timezone.utc),
        quality=FactQuality.DERIVED if derived else FactQuality.VERIFIED,
    )
