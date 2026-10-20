"""Policy rules — deterministic decision logic.

The policy rules define **what actions are allowed under what conditions**.
They are pure functions: given (machine_state, health_state, degradation_score,
root_cause, tool_name), they return a ``PolicyDecision``.

These rules are **deterministic** — the same inputs always produce the same
output. The LLM cannot override them. This is the security boundary.

Rule structure:
- Each rule is a function that takes a ``PolicyContext`` and returns a ``PolicyDecisionResult``.
- Rules are evaluated in priority order.
- The first matching rule wins.
- If no rule matches, the default is DENY.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from factorymind.domain.enums import (
    FailureMode,
    HealthState,
    MachineState,
    PolicyDecision,
    ToolName,
)
from factorymind.domain.models import PolicyDecisionResult
from factorymind.policy.permissions import PermissionLevel, get_permission, is_auto_approved, requires_human_approval


@dataclass(frozen=True)
class PolicyContext:
    """Context for policy evaluation.

    Encapsulates everything the policy engine needs to make a decision.
    The LLM/agent constructs this context, but the policy engine owns the
    decision.
    """

    machine_id: str
    machine_state: MachineState
    health_state: HealthState
    degradation_score: float
    root_cause: FailureMode
    tool_name: ToolName
    has_approval: bool = False
    approval_level: str = ""  # "operator", "supervisor", ""


# Type alias for a policy rule function.
PolicyRuleFn = Callable[[PolicyContext], PolicyDecisionResult | None]


def _deny(ctx: PolicyContext, reason: str) -> PolicyDecisionResult:
    return PolicyDecisionResult(
        decision=PolicyDecision.DENY,
        tool_name=ctx.tool_name,
        machine_id=ctx.machine_id,
        reason=reason,
    )


def _allow(ctx: PolicyContext, reason: str) -> PolicyDecisionResult:
    return PolicyDecisionResult(
        decision=PolicyDecision.ALLOW,
        tool_name=ctx.tool_name,
        machine_id=ctx.machine_id,
        reason=reason,
    )


def _require_approval(ctx: PolicyContext, reason: str, conditions: list[str] | None = None) -> PolicyDecisionResult:
    return PolicyDecisionResult(
        decision=PolicyDecision.REQUIRE_APPROVAL,
        tool_name=ctx.tool_name,
        machine_id=ctx.machine_id,
        reason=reason,
        required_approval=True,
        conditions=conditions or [],
    )


# --- Policy Rules (evaluated in order, first match wins) ---


def rule_machine_shutdown_blocks_all(ctx: PolicyContext) -> PolicyDecisionResult | None:
    """If the machine is already shut down, deny all actions except status reads."""
    if ctx.machine_state == MachineState.SHUTDOWN:
        if ctx.tool_name in (ToolName.GET_MACHINE_STATUS, ToolName.GET_SENSOR_HISTORY):
            return _allow(ctx, "Read-only access permitted on shutdown machine.")
        return _deny(ctx, "Machine is shut down — no actions allowed.")
    return None


def rule_maintenance_blocks_actions(ctx: PolicyContext) -> PolicyDecisionResult | None:
    """During maintenance, deny all machine-affecting actions."""
    if ctx.machine_state == MachineState.MAINTENANCE:
        if ctx.tool_name in (ToolName.GET_MACHINE_STATUS, ToolName.GET_SENSOR_HISTORY):
            return _allow(ctx, "Read-only access permitted during maintenance.")
        return _deny(ctx, "Machine is in maintenance — no actions allowed.")
    return None


def rule_readonly_tools_always_allowed(ctx: PolicyContext) -> PolicyDecisionResult | None:
    """Read-only tools (status, history) are always allowed."""
    if ctx.tool_name in (ToolName.GET_MACHINE_STATUS, ToolName.GET_SENSOR_HISTORY):
        return _allow(ctx, "Read-only tool permitted.")
    return None


def rule_schedule_inspection_allowed(ctx: PolicyContext) -> PolicyDecisionResult | None:
    """Schedule inspection is allowed when degradation or anomalies are present."""
    if ctx.tool_name == ToolName.SCHEDULE_INSPECTION:
        if ctx.degradation_score >= 0.2 or ctx.root_cause != FailureMode.NONE:
            return _allow(ctx, "Inspection scheduled — degradation or anomaly detected.")
        return _deny(ctx, "No degradation or anomaly — inspection not warranted.")
    return None


def rule_reduce_load_requires_approval(ctx: PolicyContext) -> PolicyDecisionResult | None:
    """Reduce load requires operator approval when degradation is significant."""
    if ctx.tool_name == ToolName.REDUCE_MACHINE_LOAD:
        if ctx.degradation_score >= 0.5:
            if ctx.has_approval:
                return _allow(ctx, "Load reduction approved by operator.")
            return _require_approval(
                ctx,
                "Load reduction requires operator approval for significant degradation.",
                conditions=["operator_approval"],
            )
        return _deny(ctx, "Load reduction not warranted — degradation below threshold.")
    return None


def rule_shutdown_requires_supervisor(ctx: PolicyContext) -> PolicyDecisionResult | None:
    """Shutdown requires supervisor approval and critical state."""
    if ctx.tool_name == ToolName.SHUTDOWN_MACHINE:
        if ctx.health_state not in (HealthState.SEVERE_DEGRADATION, HealthState.CRITICAL_FAILURE):
            return _deny(ctx, "Shutdown not warranted — machine not in critical state.")

        if not ctx.has_approval or ctx.approval_level != "supervisor":
            return _require_approval(
                ctx,
                "Shutdown requires supervisor approval for critical machines.",
                conditions=["supervisor_approval"],
            )

        return _allow(ctx, "Shutdown approved by supervisor for critical machine.")
    return None


def rule_request_approval_always_allowed(ctx: PolicyContext) -> PolicyDecisionResult | None:
    """Requesting human approval is always allowed."""
    if ctx.tool_name == ToolName.REQUEST_HUMAN_APPROVAL:
        return _allow(ctx, "Approval request permitted.")
    return None


def rule_default_deny(ctx: PolicyContext) -> PolicyDecisionResult:
    """Default: deny any unhandled action."""
    return _deny(ctx, f"No policy rule matched for tool {ctx.tool_name.value}.")


# Ordered list of policy rules.
POLICY_RULES: list[PolicyRuleFn] = [
    rule_machine_shutdown_blocks_all,
    rule_maintenance_blocks_actions,
    rule_readonly_tools_always_allowed,
    rule_schedule_inspection_allowed,
    rule_reduce_load_requires_approval,
    rule_shutdown_requires_supervisor,
    rule_request_approval_always_allowed,
    # Default must be last.
    rule_default_deny,
]