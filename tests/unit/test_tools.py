"""Tests for the tool registry, broker, and machine tools.

Critical invariant: the agent CANNOT bypass the broker. All dangerous actions
must go through the broker, which enforces policy and audit.
"""

from __future__ import annotations

import pytest

from factorymind.domain.enums import (
    FailureMode,
    HealthState,
    MachineState,
    ToolName,
)
from factorymind.tools.broker import ExecutionDenied, ToolBroker
from factorymind.tools.machine_tools import reset_machine_state, get_machine_state
from factorymind.tools.registry import ToolRegistry


class TestToolRegistry:
    def test_all_tools_registered(self, tool_registry):
        names = tool_registry.list_tool_names()
        assert ToolName.GET_MACHINE_STATUS in names
        assert ToolName.SCHEDULE_INSPECTION in names
        assert ToolName.REDUCE_MACHINE_LOAD in names
        assert ToolName.SHUTDOWN_MACHINE in names

    def test_get_existing_tool(self, tool_registry):
        tool = tool_registry.get(ToolName.SCHEDULE_INSPECTION)
        assert tool is not None
        assert tool.name == ToolName.SCHEDULE_INSPECTION

    def test_get_nonexistent_tool(self, tool_registry):
        # Use a valid ToolName that isn't registered
        tool_registry._tools.clear()
        assert tool_registry.get(ToolName.SCHEDULE_INSPECTION) is None

    def test_input_validation(self, tool_registry):
        tool = tool_registry.get(ToolName.REDUCE_MACHINE_LOAD)
        assert tool is not None
        # Valid input
        errors = tool.validate_input({"reduction_percent": 20.0})
        assert errors == []
        # Missing required param
        errors = tool.validate_input({})
        assert len(errors) > 0
        # Wrong type
        errors = tool.validate_input({"reduction_percent": "twenty"})
        assert len(errors) > 0
        # Unexpected param
        errors = tool.validate_input({"reduction_percent": 20.0, "extra": True})
        assert len(errors) > 0


class TestToolBroker:
    def test_execute_readonly_tool(self, tool_broker):
        result = tool_broker.request_execution(
            tool_name=ToolName.GET_MACHINE_STATUS,
            machine_id="M-1",
            machine_state=MachineState.RUNNING,
            health_state=HealthState.HEALTHY,
            degradation_score=0.0,
            root_cause=FailureMode.NONE,
        )
        assert result.success is True
        assert result.tool_name == ToolName.GET_MACHINE_STATUS

    def test_execute_schedule_inspection_with_degradation(self, tool_broker):
        result = tool_broker.request_execution(
            tool_name=ToolName.SCHEDULE_INSPECTION,
            machine_id="M-1",
            machine_state=MachineState.WARNING,
            health_state=HealthState.DEVELOPING_FAULT,
            degradation_score=0.5,
            root_cause=FailureMode.BEARING_DEGRADATION,
        )
        assert result.success is True
        assert "inspection_scheduled_at" in result.output

    def test_schedule_inspection_denied_on_healthy(self, tool_broker):
        with pytest.raises(ExecutionDenied):
            tool_broker.request_execution(
                tool_name=ToolName.SCHEDULE_INSPECTION,
                machine_id="M-1",
                machine_state=MachineState.RUNNING,
                health_state=HealthState.HEALTHY,
                degradation_score=0.0,
                root_cause=FailureMode.NONE,
            )

    def test_reduce_load_requires_approval(self, tool_broker):
        with pytest.raises(ExecutionDenied) as exc_info:
            tool_broker.request_execution(
                tool_name=ToolName.REDUCE_MACHINE_LOAD,
                machine_id="M-1",
                params={"reduction_percent": 20.0},
                machine_state=MachineState.CRITICAL,
                health_state=HealthState.SEVERE_DEGRADATION,
                degradation_score=0.7,
                root_cause=FailureMode.BEARING_DEGRADATION,
                has_approval=False,
            )
        assert exc_info.value.decision.required_approval is True

    def test_reduce_load_with_approval(self, tool_broker):
        result = tool_broker.request_execution(
            tool_name=ToolName.REDUCE_MACHINE_LOAD,
            machine_id="M-1",
            params={"reduction_percent": 25.0},
            machine_state=MachineState.CRITICAL,
            health_state=HealthState.SEVERE_DEGRADATION,
            degradation_score=0.7,
            root_cause=FailureMode.BEARING_DEGRADATION,
            has_approval=True,
            approval_level="operator",
        )
        assert result.success is True
        assert result.output["reduction_percent"] == 25.0

    # --- CRITICAL SECURITY TESTS ---

    def test_shutdown_denied_without_approval(self, tool_broker):
        """Agent requests shutdown without approval → DENIED."""
        reset_machine_state("M-SEC-1")
        with pytest.raises(ExecutionDenied):
            tool_broker.request_execution(
                tool_name=ToolName.SHUTDOWN_MACHINE,
                machine_id="M-SEC-1",
                params={"reason": "Agent thinks machine is failing"},
                machine_state=MachineState.CRITICAL,
                health_state=HealthState.CRITICAL_FAILURE,
                degradation_score=0.98,
                root_cause=FailureMode.BEARING_FAILURE,
                has_approval=False,
            )

    def test_shutdown_with_supervisor_approval(self, tool_broker):
        """Supervisor approval + critical state → shutdown executes."""
        reset_machine_state("M-SEC-2")
        result = tool_broker.request_execution(
            tool_name=ToolName.SHUTDOWN_MACHINE,
            machine_id="M-SEC-2",
            params={"reason": "Critical bearing failure"},
            machine_state=MachineState.CRITICAL,
            health_state=HealthState.CRITICAL_FAILURE,
            degradation_score=0.98,
            root_cause=FailureMode.BEARING_FAILURE,
            has_approval=True,
            approval_level="supervisor",
        )
        assert result.success is True
        assert result.output["new_state"] == "shutdown"

    def test_shutdown_on_healthy_machine_denied(self, tool_broker):
        """Agent requests shutdown on healthy machine → DENIED even with approval."""
        with pytest.raises(ExecutionDenied):
            tool_broker.request_execution(
                tool_name=ToolName.SHUTDOWN_MACHINE,
                machine_id="M-SEC-3",
                params={"reason": "Agent override"},
                machine_state=MachineState.RUNNING,
                health_state=HealthState.HEALTHY,
                degradation_score=0.0,
                root_cause=FailureMode.NONE,
                has_approval=True,
                approval_level="supervisor",
            )

    def test_execution_audited(self, tool_broker, audit_chain):
        """Every tool execution must be recorded in the audit chain."""
        initial_count = audit_chain.length
        tool_broker.request_execution(
            tool_name=ToolName.GET_MACHINE_STATUS,
            machine_id="M-AUDIT-1",
            machine_state=MachineState.RUNNING,
            health_state=HealthState.HEALTHY,
            degradation_score=0.0,
            root_cause=FailureMode.NONE,
        )
        assert audit_chain.length > initial_count

    def test_denied_execution_audited(self, tool_broker, audit_chain):
        """Denied executions must also be audited."""
        initial_count = audit_chain.length
        with pytest.raises(ExecutionDenied):
            tool_broker.request_execution(
                tool_name=ToolName.SHUTDOWN_MACHINE,
                machine_id="M-AUDIT-2",
                params={"reason": "test"},
                machine_state=MachineState.RUNNING,
                health_state=HealthState.HEALTHY,
                degradation_score=0.0,
                root_cause=FailureMode.NONE,
            )
        assert audit_chain.length > initial_count

    def test_invalid_input_rejected(self, tool_broker):
        """Malformed input must be rejected before execution."""
        with pytest.raises(ExecutionDenied):
            tool_broker.request_execution(
                tool_name=ToolName.REDUCE_MACHINE_LOAD,
                machine_id="M-1",
                params={},  # missing required param
                machine_state=MachineState.CRITICAL,
                health_state=HealthState.SEVERE_DEGRADATION,
                degradation_score=0.7,
                root_cause=FailureMode.BEARING_DEGRADATION,
                has_approval=True,
                approval_level="operator",
            )

    def test_nonexistent_tool_denied(self, tool_broker):
        """Requesting a non-existent tool must be denied."""
        # Temporarily remove all tools from registry
        tool_broker._registry._tools.clear()
        with pytest.raises(ExecutionDenied):
            tool_broker.request_execution(
                tool_name=ToolName.GET_MACHINE_STATUS,
                machine_id="M-1",
                machine_state=MachineState.RUNNING,
                health_state=HealthState.HEALTHY,
                degradation_score=0.0,
                root_cause=FailureMode.NONE,
            )