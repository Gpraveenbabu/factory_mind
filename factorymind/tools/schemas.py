"""Tool schemas — input/output definitions for all registered tools.

Each tool has a JSON-schema-like input definition that the ToolBroker validates
before execution. This prevents malformed or malicious inputs from reaching
the machine.

The schemas use Python dataclasses for type safety and are validated at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from factorymind.domain.enums import RiskLevel, ToolName
from factorymind.domain.models import ToolExecutionResult


# Type alias for a tool handler function.
class ToolHandler(Protocol):
    """Protocol for tool handler functions."""

    def __call__(self, machine_id: str, params: dict[str, Any]) -> ToolExecutionResult:
        ...


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of one registered tool.

    Attributes:
        name: Canonical tool name.
        description: What the tool does.
        risk_level: Risk level (LOW, MEDIUM, HIGH, CRITICAL).
        required_permission: Required permission level string.
        input_schema: Expected input keys and types.
        handler: Callable that executes the tool.
    """

    name: ToolName
    description: str
    risk_level: RiskLevel
    required_permission: str
    input_schema: dict[str, type]
    handler: ToolHandler

    def validate_input(self, params: dict[str, Any]) -> list[str]:
        """Validate input parameters against the schema.

        Returns a list of error messages (empty if valid).
        """
        errors: list[str] = []
        for key, expected_type in self.input_schema.items():
            if key not in params:
                errors.append(f"Missing required parameter: {key}")
            elif not isinstance(params[key], expected_type):
                errors.append(
                    f"Parameter '{key}' must be {expected_type.__name__}, "
                    f"got {type(params[key]).__name__}"
                )

        # Check for unexpected parameters.
        for key in params:
            if key not in self.input_schema:
                errors.append(f"Unexpected parameter: {key}")

        return errors