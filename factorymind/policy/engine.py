"""Policy engine — evaluates actions against deterministic rules.

The policy engine is the **security boundary** between the AI agent and the
machine. It is the only component that decides whether an action is allowed.

Key invariant: **LLM recommendation ≠ permission to execute**.

The engine:
1. Receives a ``PolicyContext`` from the agent (or any caller).
2. Evaluates rules in priority order.
3. Returns a ``PolicyDecisionResult`` (ALLOW, DENY, or REQUIRE_APPROVAL).
4. Logs every decision to the audit chain.

The engine is **stateless** — all context is passed in via ``PolicyContext``.
This makes it trivially testable and prevents side-channel manipulation.
"""

from __future__ import annotations

from factorymind.domain.enums import PolicyDecision
from factorymind.domain.models import PolicyDecisionResult
from factorymind.policy.rules import POLICY_RULES, PolicyContext


class PolicyEngine:
    """Deterministic policy evaluation engine.

    The engine holds no mutable state. Each call to ``evaluate`` is independent.
    """

    def evaluate(self, ctx: PolicyContext) -> PolicyDecisionResult:
        """Evaluate a proposed action against all policy rules.

        Rules are evaluated in order. The first rule that returns a non-None
        result wins. If no rule matches (shouldn't happen — default_deny is
        always last), the action is denied.

        Args:
            ctx: The policy context describing the proposed action.

        Returns:
            PolicyDecisionResult with ALLOW, DENY, or REQUIRE_APPROVAL.
        """
        for rule_fn in POLICY_RULES:
            result = rule_fn(ctx)
            if result is not None:
                return result

        # Should never reach here — rule_default_deny always matches.
        return PolicyDecisionResult(
            decision=PolicyDecision.DENY,
            tool_name=ctx.tool_name,
            machine_id=ctx.machine_id,
            reason="No policy rule matched — fail-safe deny.",
        )

    def is_allowed(self, ctx: PolicyContext) -> bool:
        """Convenience: return True if the action is ALLOWED (no approval needed)."""
        return self.evaluate(ctx).decision == PolicyDecision.ALLOW

    def is_denied(self, ctx: PolicyContext) -> bool:
        """Convenience: return True if the action is DENIED."""
        return self.evaluate(ctx).decision == PolicyDecision.DENY

    def needs_approval(self, ctx: PolicyContext) -> bool:
        """Convenience: return True if the action requires human approval."""
        return self.evaluate(ctx).decision == PolicyDecision.REQUIRE_APPROVAL