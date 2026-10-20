"""Domain models (dataclasses) for FactoryMind.

These are plain Python dataclasses, **not** ORM models. They represent the core
business entities that flow through every layer. Database ORM models (Phase 4)
and Pydantic API schemas (Phase 4) will map to/from these.

Design rules:
- Immutable where practical (``frozen=True``).
- No business logic — only data + maybe simple factory methods.
- No external dependencies (no SQLAlchemy, no Pydantic here).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from factorymind.domain.enums import (
    AnomalyType,
    ApprovalStatus,
    AuditEventType,
    FailureMode,
    HealthState,
    MachineState,
    PolicyDecision,
    RiskLevel,
    ToolName,
)


def utc_now() -> datetime:
    """Return timezone-aware UTC now — single source of truth for timestamps."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SensorReading:
    """A single timestamped reading for one sensor on one machine."""

    machine_id: str
    timestamp: datetime
    sensor_name: str
    value: float
    quality: float = 1.0  # 1.0 = good, 0.0 = bad/missing


@dataclass(frozen=True)
class TelemetrySnapshot:
    """All sensor readings for one machine at one timestamp."""

    machine_id: str
    timestamp: datetime
    readings: dict[str, float]  # sensor_name -> value (NaN if missing)
    quality: dict[str, float] = field(default_factory=dict)  # sensor_name -> quality


@dataclass(frozen=True)
class MachineConfig:
    """Static configuration for a simulated machine."""

    machine_id: str
    model: str = "FM-2000"
    installed_date: datetime = field(default_factory=utc_now)
    nominal_rpm: float = 1500.0
    nominal_load: float = 55.0


@dataclass
class MachineRuntimeState:
    """Mutable runtime state of a machine (not persisted directly)."""

    machine_id: str
    state: MachineState = MachineState.RUNNING
    health: HealthState = HealthState.HEALTHY
    degradation_score: float = 0.0
    failure_probability: float = 0.0
    rul_minutes: float | None = None
    current_step: int = 0
    active_failure: FailureMode = FailureMode.NONE
    failure_progress: float = 0.0  # 0..1
    last_updated: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class Anomaly:
    """An anomaly detected by any detector."""

    machine_id: str
    timestamp: datetime
    sensor_name: str
    anomaly_type: AnomalyType
    severity: float  # 0..1
    value: float
    threshold: float | None = None
    message: str = ""
    detector_name: str = ""


@dataclass(frozen=True)
class FeatureVector:
    """Computed features for one machine at one timestamp."""

    machine_id: str
    timestamp: datetime
    features: dict[str, float]
    source_window: int = 0  # how many readings were used


@dataclass(frozen=True)
class EvidenceItem:
    """A single piece of evidence used in root-cause analysis."""

    source: str  # e.g. "vibration_trend", "temperature_threshold"
    description: str
    value: float | None = None
    expected: float | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class RootCauseResult:
    """Output of the RCA engine."""

    machine_id: str
    timestamp: datetime
    root_cause: FailureMode
    confidence: float  # 0..1
    evidence: list[EvidenceItem]
    health_state: HealthState
    degradation_score: float


@dataclass(frozen=True)
class PolicyDecisionResult:
    """Output of the policy engine for a proposed action."""

    decision: PolicyDecision
    tool_name: ToolName
    machine_id: str
    reason: str
    required_approval: bool = False
    conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ApprovalRequest:
    """A human-in-the-loop approval request."""

    request_id: str
    machine_id: str
    tool_name: ToolName
    requested_by: str  # actor: "agent", "operator", "system"
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=utc_now)
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_reason: str = ""
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ToolExecutionResult:
    """Result of executing a tool through the broker."""

    tool_name: ToolName
    machine_id: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    executed_at: datetime = field(default_factory=utc_now)
    approved_by: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    """A single event in the tamper-evident audit chain."""

    event_id: str
    timestamp: datetime
    machine_id: str
    actor: str
    event_type: AuditEventType
    payload: dict[str, Any]
    previous_hash: str = ""
    event_hash: str = ""


@dataclass(frozen=True)
class Incident:
    """An incident aggregating related events for one machine."""

    incident_id: str
    machine_id: str
    created_at: datetime
    status: str = "open"
    root_cause: FailureMode | None = None
    actions_taken: list[str] = field(default_factory=list)
    resolved_at: datetime | None = None