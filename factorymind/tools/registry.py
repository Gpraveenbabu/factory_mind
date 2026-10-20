"""Tool registry — central catalog of all registered tools.

The registry is a lookup table that maps tool names to their definitions.
It is populated at startup and is immutable after registration.

The ToolBroker uses the registry to:
1. Check if a tool exists.
2. Validate input schemas.
3. Look up risk levels and required permissions.
4. Dispatch to the handler.

This separation ensures the broker never hard-codes tool knowledge.
"""

from __future__ import annotations

from factorymind.domain.enums import RiskLevel, ToolName
from factorymind.tools import machine_tools
from factorymind.tools.schemas import ToolDefinition


class ToolRegistry:
    """Registry of all available tools."""

    def __init__(self) -> None:
        self._tools: dict[ToolName, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register all default machine tools."""
        self.register(ToolDefinition(
            name=ToolName.GET_MACHINE_STATUS,
            description="Retrieve the current status of a machine.",
            risk_level=RiskLevel.LOW,
            required_permission="system",
            input_schema={},
            handler=machine_tools.get_machine_status_handler,
        ))

        self.register(ToolDefinition(
            name=ToolName.GET_SENSOR_HISTORY,
            description="Retrieve sensor history for a machine.",
            risk_level=RiskLevel.LOW,
            required_permission="system",
            input_schema={"window": int},
            handler=machine_tools.get_sensor_history_handler,
        ))

        self.register(ToolDefinition(
            name=ToolName.SCHEDULE_INSPECTION,
            description="Schedule a maintenance inspection for a machine.",
            risk_level=RiskLevel.LOW,
            required_permission="system",
            input_schema={},
            handler=machine_tools.schedule_inspection_handler,
        ))

        self.register(ToolDefinition(
            name=ToolName.REDUCE_MACHINE_LOAD,
            description="Reduce the load on a machine to mitigate stress.",
            risk_level=RiskLevel.MEDIUM,
            required_permission="operator",
            input_schema={"reduction_percent": float},
            handler=machine_tools.reduce_machine_load_handler,
        ))

        self.register(ToolDefinition(
            name=ToolName.SHUTDOWN_MACHINE,
            description="Shut down a machine to prevent catastrophic failure.",
            risk_level=RiskLevel.CRITICAL,
            required_permission="supervisor",
            input_schema={"reason": str},
            handler=machine_tools.shutdown_machine_handler,
        ))

        self.register(ToolDefinition(
            name=ToolName.REQUEST_HUMAN_APPROVAL,
            description="Request human approval for an action.",
            risk_level=RiskLevel.LOW,
            required_permission="system",
            input_schema={"reason": str},
            handler=machine_tools.request_human_approval_handler,
        ))

    def register(self, definition: ToolDefinition) -> None:
        """Register a new tool."""
        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name}")
        self._tools[definition.name] = definition

    def get(self, name: ToolName) -> ToolDefinition | None:
        """Look up a tool by name. Returns None if not found."""
        return self._tools.get(name)

    def exists(self, name: ToolName) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._tools.values())

    def list_tool_names(self) -> list[ToolName]:
        """Return all registered tool names."""
        return list(self._tools.keys())