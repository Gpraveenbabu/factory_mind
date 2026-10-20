"""Machine tool handlers — the actual execution logic for each tool.

Each handler receives (machine_id, params) and returns a ``ToolExecutionResult``.
Handlers are intentionally simple in Phase 1 — they simulate the machine action.
In production, these would interface with SCADA/PLC systems.

Important: handlers do NOT check permissions or policy. That is the broker's
job. Handlers only execute.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from factorymind.domain.enums import MachineState, ToolName
from factorymind.domain.models import ToolExecutionResult


# Shared in-memory machine state store (Phase 1).
# In production, this would be the actual machine control system.
_machine_states: dict[str, MachineState] = {}
_machine_loads: dict[str, float] = {}
_inspections_scheduled: dict[str, list[datetime]] = {}


def _ensure_machine(machine_id: str) -> None:
    """Ensure a machine exists in the in-memory store."""
    if machine_id not in _machine_states:
        _machine_states[machine_id] = MachineState.RUNNING
        _machine_loads[machine_id] = 55.0
        _inspections_scheduled[machine_id] = []


def get_machine_status_handler(machine_id: str, params: dict[str, Any]) -> ToolExecutionResult:
    """Handler for GET_MACHINE_STATUS."""
    _ensure_machine(machine_id)
    return ToolExecutionResult(
        tool_name=ToolName.GET_MACHINE_STATUS,
        machine_id=machine_id,
        success=True,
        output={
            "machine_id": machine_id,
            "state": _machine_states[machine_id].value,
            "load": _machine_loads.get(machine_id, 55.0),
            "inspections_scheduled": len(_inspections_scheduled.get(machine_id, [])),
        },
    )


def get_sensor_history_handler(machine_id: str, params: dict[str, Any]) -> ToolExecutionResult:
    """Handler for GET_SENSOR_HISTORY.

    In Phase 1, returns a placeholder. The real implementation will pull from
    the ingestion pipeline's buffer.
    """
    _ensure_machine(machine_id)
    return ToolExecutionResult(
        tool_name=ToolName.GET_SENSOR_HISTORY,
        machine_id=machine_id,
        success=True,
        output={
            "machine_id": machine_id,
            "message": "Sensor history retrieval — connect to ingestion buffer in production.",
        },
    )


def schedule_inspection_handler(machine_id: str, params: dict[str, Any]) -> ToolExecutionResult:
    """Handler for SCHEDULE_INSPECTION."""
    _ensure_machine(machine_id)
    now = datetime.now(timezone.utc)
    _inspections_scheduled[machine_id].append(now)
    return ToolExecutionResult(
        tool_name=ToolName.SCHEDULE_INSPECTION,
        machine_id=machine_id,
        success=True,
        output={
            "machine_id": machine_id,
            "inspection_scheduled_at": now.isoformat(),
            "total_inspections": len(_inspections_scheduled[machine_id]),
        },
    )


def reduce_machine_load_handler(machine_id: str, params: dict[str, Any]) -> ToolExecutionResult:
    """Handler for REDUCE_MACHINE_LOAD."""
    _ensure_machine(machine_id)
    reduction = params.get("reduction_percent", 20.0)
    current_load = _machine_loads.get(machine_id, 55.0)
    new_load = max(0.0, current_load - reduction)
    _machine_loads[machine_id] = new_load
    return ToolExecutionResult(
        tool_name=ToolName.REDUCE_MACHINE_LOAD,
        machine_id=machine_id,
        success=True,
        output={
            "machine_id": machine_id,
            "previous_load": current_load,
            "new_load": new_load,
            "reduction_percent": reduction,
        },
    )


def shutdown_machine_handler(machine_id: str, params: dict[str, Any]) -> ToolExecutionResult:
    """Handler for SHUTDOWN_MACHINE."""
    _ensure_machine(machine_id)
    previous_state = _machine_states[machine_id]
    _machine_states[machine_id] = MachineState.SHUTDOWN
    return ToolExecutionResult(
        tool_name=ToolName.SHUTDOWN_MACHINE,
        machine_id=machine_id,
        success=True,
        output={
            "machine_id": machine_id,
            "previous_state": previous_state.value,
            "new_state": MachineState.SHUTDOWN.value,
            "shutdown_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def request_human_approval_handler(machine_id: str, params: dict[str, Any]) -> ToolExecutionResult:
    """Handler for REQUEST_HUMAN_APPROVAL.

    In Phase 1, this is a no-op that returns a confirmation. The human-in-the-loop
    component (Phase 7) will manage actual approval workflows.
    """
    _ensure_machine(machine_id)
    return ToolExecutionResult(
        tool_name=ToolName.REQUEST_HUMAN_APPROVAL,
        machine_id=machine_id,
        success=True,
        output={
            "machine_id": machine_id,
            "message": "Human approval requested.",
            "reason": params.get("reason", "No reason provided."),
        },
    )


def reset_machine_state(machine_id: str) -> None:
    """Reset a machine to RUNNING state (for testing)."""
    _ensure_machine(machine_id)
    _machine_states[machine_id] = MachineState.RUNNING
    _machine_loads[machine_id] = 55.0


def get_machine_state(machine_id: str) -> MachineState:
    """Return the current in-memory machine state (for testing)."""
    _ensure_machine(machine_id)
    return _machine_states[machine_id]