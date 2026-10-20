"""Tests for the policy engine — the security boundary.

Critical invariant tested here: **LLM recommendation ≠ permission to execute**.
The policy engine must deny unsafe actions regardless of what the agent requests.
"""

from __future__ import annotations

import pytest

from factorymind.domain.enums import (
    FailureMode,
    HealthState,
    MachineState,
    PolicyDecision,
    ToolName,
)
from factorymind.domain.models import MachineConfig
from factorymind.policy.engine import PolicyEngine
from factorymind.policy.rules import PolicyContext
from factorymind.simulation.machine import MachineSimulator


class TestPolicyEngine:
    def test_readonly_tools_always_allowed(self, policy_engine):
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.RUNNING,
            health_state=HealthState.HEALTHY,
            degradation_score=0.0,
            root_cause=FailureMode.NONE,
            tool_name=ToolName.GET_MACHINE_STATUS,
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_schedule_inspection_denied_on_healthy(self, policy_engine):
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.RUNNING,
            health_state=HealthState.HEALTHY,
            degradation_score=0.0,
            root_cause=FailureMode.NONE,
            tool_name=ToolName.SCHEDULE_INSPECTION,
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.DENY

    def test_schedule_inspection_allowed_on_degradation(self, policy_engine):
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.WARNING,
            health_state=HealthState.DEVELOPING_FAULT,
            degradation_score=0.6,
            root_cause=FailureMode.BEARING_DEGRADATION,
            tool_name=ToolName.SCHEDULE_INSPECTION,
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_reduce_load_requires_approval(self, policy_engine):
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.CRITICAL,
            health_state=HealthState.SEVERE_DEGRADATION,
            degradation_score=0.7,
            root_cause=FailureMode.BEARING_DEGRADATION,
            tool_name=ToolName.REDUCE_MACHINE_LOAD,
            has_approval=False,
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.REQUIRE_APPROVAL
        assert result.required_approval is True

    def test_reduce_load_allowed_with_approval(self, policy_engine):
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.CRITICAL,
            health_state=HealthState.SEVERE_DEGRADATION,
            degradation_score=0.7,
            root_cause=FailureMode.BEARING_DEGRADATION,
            tool_name=ToolName.REDUCE_MACHINE_LOAD,
            has_approval=True,
            approval_level="operator",
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_reduce_load_denied_below_threshold(self, policy_engine):
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.RUNNING,
            health_state=HealthState.HEALTHY,
            degradation_score=0.1,
            root_cause=FailureMode.NONE,
            tool_name=ToolName.REDUCE_MACHINE_LOAD,
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.DENY

    # --- CRITICAL SECURITY TESTS ---

    def test_shutdown_denied_on_healthy_machine(self, policy_engine):
        """An agent requesting shutdown on a healthy machine must be DENIED."""
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.RUNNING,
            health_state=HealthState.HEALTHY,
            degradation_score=0.0,
            root_cause=FailureMode.NONE,
            tool_name=ToolName.SHUTDOWN_MACHINE,
            has_approval=True,  # Even WITH approval
            approval_level="supervisor",
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.DENY

    def test_shutdown_requires_supervisor_approval(self, policy_engine):
        """Shutdown on critical machine requires supervisor approval."""
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.CRITICAL,
            health_state=HealthState.CRITICAL_FAILURE,
            degradation_score=0.98,
            root_cause=FailureMode.BEARING_FAILURE,
            tool_name=ToolName.SHUTDOWN_MACHINE,
            has_approval=False,
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.REQUIRE_APPROVAL

    def test_shutdown_with_operator_approval_still_denied(self, policy_engine):
        """Operator approval is NOT sufficient for shutdown — supervisor required."""
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.CRITICAL,
            health_state=HealthState.CRITICAL_FAILURE,
            degradation_score=0.98,
            root_cause=FailureMode.BEARING_FAILURE,
            tool_name=ToolName.SHUTDOWN_MACHINE,
            has_approval=True,
            approval_level="operator",  # Not supervisor!
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.REQUIRE_APPROVAL

    def test_shutdown_allowed_with_supervisor_approval_on_critical(self, policy_engine):
        """Supervisor approval + critical state = shutdown allowed."""
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.CRITICAL,
            health_state=HealthState.CRITICAL_FAILURE,
            degradation_score=0.98,
            root_cause=FailureMode.BEARING_FAILURE,
            tool_name=ToolName.SHUTDOWN_MACHINE,
            has_approval=True,
            approval_level="supervisor",
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_no_action_on_shutdown_machine(self, policy_engine):
        """Once shut down, no actions except reads are allowed."""
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.SHUTDOWN,
            health_state=HealthState.CRITICAL_FAILURE,
            degradation_score=1.0,
            root_cause=FailureMode.BEARING_FAILURE,
            tool_name=ToolName.REDUCE_MACHINE_LOAD,
            has_approval=True,
            approval_level="supervisor",
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.DENY

    def test_no_action_on_maintenance_machine(self, policy_engine):
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.MAINTENANCE,
            health_state=HealthState.HEALTHY,
            degradation_score=0.0,
            root_cause=FailureMode.NONE,
            tool_name=ToolName.SCHEDULE_INSPECTION,
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.DENY

    def test_default_deny_for_unknown_combination(self, policy_engine):
        """Any unhandled action should be denied (fail-safe)."""
        ctx = PolicyContext(
            machine_id="M-1",
            machine_state=MachineState.RUNNING,
            health_state=HealthState.HEALTHY,
            degradation_score=0.0,
            root_cause=FailureMode.NONE,
            tool_name=ToolName.SHUTDOWN_MACHINE,
            has_approval=False,
        )
        result = policy_engine.evaluate(ctx)
        assert result.decision == PolicyDecision.DENY

    # --- INVARIANT: LLM recommendation ≠ permission ---

    def test_agent_recommendation_does_not_grant_permission(self, policy_engine):
        """The most important test: agent recommends shutdown → policy DENIES it.

        This proves the critical security invariant: the agent's recommendation
        is not sufficient to execute a dangerous action.
        """
        # Agent "recommends" shutdown on a machine that has early degradation
        ctx = PolicyContext(
            machine_id="M-AGENT-TEST",
            machine_state=MachineState.DEGRADING,
            health_state=HealthState.EARLY_DEGRADATION,
            degradation_score=0.3,
            root_cause=FailureMode.BEARING_DEGRADATION,
            tool_name=ToolName.SHUTDOWN_MACHINE,
            has_approval=True,  # Agent claims approval
            approval_level="operator",  # But only operator level
        )
        result = policy_engine.evaluate(ctx)
        # Machine not in critical state → DENY regardless of agent's wishes
        assert result.decision == PolicyDecision.DENY
        assert "not in critical state" in result.reason.lower()