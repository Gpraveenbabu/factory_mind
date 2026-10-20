"""Tool broker — the ONLY component allowed to execute machine actions.

The broker is the enforcement point. It:
1. Checks the tool exists in the registry.
2. Validates the input schema.
3. Evaluates the policy engine.
4. Checks human approval if required.
5. Executes the tool handler.
6. Records everything to the audit chain.

The agent CANNOT bypass the broker. The agent constructs a request, the
broker decides whether to execute it.

Key invariant: **No code path exists from the agent to the machine that does
not pass through the broker.**
"""

from __future__ import annotations

from typing import Any

from factorymind.audit.chain import AuditChain
from factorymind.domain.enums import AuditEventType, PolicyDecision, ToolName
from factorymind.domain.models import ApprovalRequest, PolicyDecisionResult, ToolExecutionResult
from factorymind.policy.engine import PolicyEngine
from factorymind.policy.permissions import PermissionLevel, get_permission
from factorymind.policy.rules import PolicyContext
from factorymind.tools.registry import ToolRegistry
from factorymind.tools.schemas import ToolDefinition


class ExecutionDenied(Exception):
    """Raised when the broker denies a tool execution request."""

    def __init__(self, decision: PolicyDecisionResult) -> None:
        self.decision = decision
        super().__init__(f"Tool execution denied: {decision.reason}")


class ToolBroker:
    """Central tool execution broker.

    Args:
        registry: The tool registry.
        policy_engine: The deterministic policy engine.
        audit_chain: The tamper-evident audit chain.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        policy_engine: PolicyEngine,
        audit_chain: AuditChain,
    ) -> None:
        self._registry = registry
        self._policy = policy_engine
        self._audit = audit_chain
        self._approvals: dict[str, ApprovalRequest] = {}

    def request_execution(
        self,
        tool_name: ToolName,
        machine_id: str,
        params: dict[str, Any] | None = None,
        actor: str = "agent",
        machine_state: Any = None,  # MachineState
        health_state: Any = None,   # HealthState
        degradation_score: float = 0.0,
        root_cause: Any = None,     # FailureMode
        has_approval: bool = False,
        approval_level: str = "",
    ) -> ToolExecutionResult:
        """Request execution of a tool.

        This is the main entry point for the agent. The broker decides
        whether to execute, deny, or require approval.

        Args:
            tool_name: Which tool to execute.
            machine_id: Target machine.
            params: Tool input parameters.
            actor: Who is requesting ("agent", "operator", "system").
            machine_state, health_state, degradation_score, root_cause:
                Current machine context for policy evaluation.
            has_approval: Whether human approval has been granted.
            approval_level: Level of approval ("operator", "supervisor").

        Returns:
            ToolExecutionResult on success.

        Raises:
            ExecutionDenied: If the policy engine denies or approval is required
                             but not granted.
        """
        params = params or {}

        # --- Step 1: Check tool exists ---
        definition = self._registry.get(tool_name)
        if definition is None:
            self._audit.record(
                machine_id=machine_id,
                actor=actor,
                event_type=AuditEventType.POLICY_DECISION,
                payload={"tool": tool_name.value, "decision": "deny", "reason": "Tool not found"},
            )
            raise ExecutionDenied(PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                tool_name=tool_name,
                machine_id=machine_id,
                reason=f"Tool not found: {tool_name.value}",
            ))

        # --- Step 2: Validate input schema ---
        errors = definition.validate_input(params)
        if errors:
            self._audit.record(
                machine_id=machine_id,
                actor=actor,
                event_type=AuditEventType.POLICY_DECISION,
                payload={"tool": tool_name.value, "decision": "deny", "reason": f"Invalid input: {errors}"},
            )
            raise ExecutionDenied(PolicyDecisionResult(
                decision=PolicyDecision.DENY,
                tool_name=tool_name,
                machine_id=machine_id,
                reason=f"Invalid input: {errors}",
            ))

        # --- Step 3: Evaluate policy ---
        ctx = PolicyContext(
            machine_id=machine_id,
            machine_state=machine_state,
            health_state=health_state,
            degradation_score=degradation_score,
            root_cause=root_cause,
            tool_name=tool_name,
            has_approval=has_approval,
            approval_level=approval_level,
        )

        decision = self._policy.evaluate(ctx)

        # --- Step 4: Handle policy decision ---
        if decision.decision == PolicyDecision.DENY:
            self._audit.record(
                machine_id=machine_id,
                actor=actor,
                event_type=AuditEventType.POLICY_DECISION,
                payload={
                    "tool": tool_name.value,
                    "decision": "deny",
                    "reason": decision.reason,
                },
            )
            raise ExecutionDenied(decision)

        if decision.decision == PolicyDecision.REQUIRE_APPROVAL:
            if not has_approval:
                self._audit.record(
                    machine_id=machine_id,
                    actor=actor,
                    event_type=AuditEventType.APPROVAL_REQUESTED,
                    payload={
                        "tool": tool_name.value,
                        "reason": decision.reason,
                        "conditions": decision.conditions,
                    },
                )
                raise ExecutionDenied(decision)

        # --- Step 5: Execute the tool ---
        result = definition.handler(machine_id, params)

        # --- Step 6: Audit the execution ---
        self._audit.record(
            machine_id=machine_id,
            actor=actor,
            event_type=AuditEventType.ACTION_EXECUTED,
            payload={
                "tool": tool_name.value,
                "params": params,
                "success": result.success,
                "output": result.output,
                "approved_by": result.approved_by or actor,
            },
        )

        # Also audit the policy decision (allow)
        self._audit.record(
            machine_id=machine_id,
            actor=actor,
            event_type=AuditEventType.POLICY_DECISION,
            payload={
                "tool": tool_name.value,
                "decision": "allow",
                "reason": decision.reason,
            },
        )

        return result

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def audit_chain(self) -> AuditChain:
        return self._audit