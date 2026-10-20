"""Permission definitions for the policy engine.

Permissions are separate from policy rules. A permission defines *who* can do
*what*. The policy engine checks permissions against the actor and the tool.

Permission levels:
- ``SYSTEM``: Automatic — no human approval needed (e.g. schedule_inspection).
- ``OPERATOR``: Requires a human operator's approval (e.g. reduce_machine_load).
- ``SUPERVISOR``: Requires supervisor approval (e.g. shutdown_machine).
- ``DENIED``: Never allowed (e.g. directly modifying sensor values).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from factorymind.domain.enums import RiskLevel, ToolName


class PermissionLevel(str, Enum):
    """Required authority level for a tool."""

    SYSTEM = "system"          # Auto-approved by the system
    OPERATOR = "operator"       # Requires operator approval
    SUPERVISOR = "supervisor"   # Requires supervisor approval
    DENIED = "denied"           # Never allowed


@dataclass(frozen=True)
class ToolPermission:
    """Permission configuration for one tool."""

    tool_name: ToolName
    risk_level: RiskLevel
    required_permission: PermissionLevel
    description: str


# --- Permission Registry ---

TOOL_PERMISSIONS: dict[ToolName, ToolPermission] = {
    ToolName.GET_MACHINE_STATUS: ToolPermission(
        tool_name=ToolName.GET_MACHINE_STATUS,
        risk_level=RiskLevel.LOW,
        required_permission=PermissionLevel.SYSTEM,
        description="Read machine status — read-only, no risk.",
    ),
    ToolName.GET_SENSOR_HISTORY: ToolPermission(
        tool_name=ToolName.GET_SENSOR_HISTORY,
        risk_level=RiskLevel.LOW,
        required_permission=PermissionLevel.SYSTEM,
        description="Read sensor history — read-only, no risk.",
    ),
    ToolName.SCHEDULE_INSPECTION: ToolPermission(
        tool_name=ToolName.SCHEDULE_INSPECTION,
        risk_level=RiskLevel.LOW,
        required_permission=PermissionLevel.SYSTEM,
        description="Schedule a maintenance inspection — low risk, system-approved.",
    ),
    ToolName.REDUCE_MACHINE_LOAD: ToolPermission(
        tool_name=ToolName.REDUCE_MACHINE_LOAD,
        risk_level=RiskLevel.MEDIUM,
        required_permission=PermissionLevel.OPERATOR,
        description="Reduce machine load — medium risk, requires operator approval.",
    ),
    ToolName.REQUEST_HUMAN_APPROVAL: ToolPermission(
        tool_name=ToolName.REQUEST_HUMAN_APPROVAL,
        risk_level=RiskLevel.LOW,
        required_permission=PermissionLevel.SYSTEM,
        description="Request human approval — system-level action.",
    ),
    ToolName.SHUTDOWN_MACHINE: ToolPermission(
        tool_name=ToolName.SHUTDOWN_MACHINE,
        risk_level=RiskLevel.CRITICAL,
        required_permission=PermissionLevel.SUPERVISOR,
        description="Shutdown machine — critical risk, requires supervisor approval.",
    ),
}


def get_permission(tool_name: ToolName) -> ToolPermission:
    """Return the permission configuration for a tool.

    Raises:
        KeyError: If the tool is not registered.
    """
    if tool_name not in TOOL_PERMISSIONS:
        raise KeyError(f"No permission defined for tool: {tool_name}")
    return TOOL_PERMISSIONS[tool_name]


def is_auto_approved(tool_name: ToolName) -> bool:
    """Check if a tool is auto-approved (no human approval needed)."""
    perm = get_permission(tool_name)
    return perm.required_permission == PermissionLevel.SYSTEM


def requires_human_approval(tool_name: ToolName) -> bool:
    """Check if a tool requires human approval."""
    perm = get_permission(tool_name)
    return perm.required_permission in (PermissionLevel.OPERATOR, PermissionLevel.SUPERVISOR)