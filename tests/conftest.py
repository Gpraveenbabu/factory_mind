"""Shared pytest fixtures for FactoryMind tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the factorymind package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factorymind.audit.chain import AuditChain
from factorymind.domain.enums import FailureMode
from factorymind.domain.models import MachineConfig
from factorymind.policy.engine import PolicyEngine
from factorymind.simulation.machine import MachineSimulator
from factorymind.tools.broker import ToolBroker
from factorymind.tools.registry import ToolRegistry


@pytest.fixture
def audit_chain() -> AuditChain:
    """Fresh audit chain for each test."""
    return AuditChain()


@pytest.fixture
def policy_engine() -> PolicyEngine:
    """Fresh policy engine for each test."""
    return PolicyEngine()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """Fresh tool registry for each test."""
    return ToolRegistry()


@pytest.fixture
def tool_broker(tool_registry, policy_engine, audit_chain) -> ToolBroker:
    """Fresh tool broker for each test."""
    return ToolBroker(tool_registry, policy_engine, audit_chain)


@pytest.fixture
def healthy_machine() -> MachineSimulator:
    """A healthy machine simulator (no failure injected)."""
    return MachineSimulator(
        config=MachineConfig(machine_id="M-TEST-001"),
        seed=42,
    )


@pytest.fixture
def bearing_degradation_machine() -> MachineSimulator:
    """A machine with gradual bearing degradation starting at step 50."""
    sim = MachineSimulator(
        config=MachineConfig(machine_id="M-BRG-TEST"),
        seed=42,
    )
    sim.inject_failure(
        mode=FailureMode.BEARING_DEGRADATION,
        onset_step=50,
        ramp_steps=150,
    )
    return sim