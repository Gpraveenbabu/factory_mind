"""Domain enumerations for FactoryMind.

All system states, failure modes, risk levels, and event types are defined here
as explicit enums. Using ``str``-based enums makes them JSON-serialisable
without custom codecs and keeps database columns human-readable.
"""

from __future__ import annotations

from enum import Enum


class MachineState(str, Enum):
    """Operational state of a machine in the control system."""

    RUNNING = "running"
    DEGRADING = "degrading"
    WARNING = "warning"
    CRITICAL = "critical"
    AWAITING_APPROVAL = "awaiting_approval"
    SHUTDOWN = "shutdown"
    MAINTENANCE = "maintenance"
    RECOVERED = "recovered"


class HealthState(str, Enum):
    """Health classification used by degradation detection."""

    HEALTHY = "healthy"
    EARLY_DEGRADATION = "early_degradation"
    DEVELOPING_FAULT = "developing_fault"
    SEVERE_DEGRADATION = "severe_degradation"
    CRITICAL_FAILURE = "critical_failure"


class FailureMode(str, Enum):
    """Supported failure modes the simulator can inject."""

    BEARING_DEGRADATION = "bearing_degradation"
    BEARING_FAILURE = "bearing_failure"
    THERMAL_OVERLOAD = "thermal_overload"
    MECHANICAL_IMBALANCE = "mechanical_imbalance"
    MOTOR_OVERLOAD = "motor_overload"
    COOLING_FAILURE = "cooling_failure"
    SENSOR_FAULT = "sensor_fault"
    NONE = "none"


class RiskLevel(str, Enum):
    """Risk level associated with a tool or action."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SensorName(str, Enum):
    """Canonical sensor identifiers used across the entire platform."""

    TEMPERATURE = "temperature"
    VIBRATION = "vibration"
    PRESSURE = "pressure"
    MOTOR_CURRENT = "motor_current"
    RPM = "rpm"
    LOAD = "load"
    COOLANT_TEMPERATURE = "coolant_temperature"
    COOLANT_FLOW = "coolant_flow"
    ACOUSTIC_LEVEL = "acoustic_level"


# Convenience list used by simulators, feature engines, and detectors.
ALL_SENSORS: tuple[str, ...] = tuple(s.value for s in SensorName)


class AnomalyType(str, Enum):
    """Type of anomaly identified by a detector."""

    THRESHOLD_BREACH = "threshold_breach"
    TREND_ANOMALY = "trend_anomaly"
    CORRELATION_ANOMALY = "correlation_anomaly"
    SENSOR_FAULT = "sensor_fault"


class AuditEventType(str, Enum):
    """Event types recorded in the tamper-evident audit chain."""

    TELEMETRY_RECEIVED = "telemetry_received"
    ANOMALY_DETECTED = "anomaly_detected"
    DEGRADATION_DETECTED = "degradation_detected"
    FAILURE_PREDICTED = "failure_predicted"
    DIAGNOSIS_CREATED = "diagnosis_created"
    RCA_PERFORMED = "rca_performed"
    RISK_CALCULATED = "risk_calculated"
    AGENT_RECOMMENDATION = "agent_recommendation"
    POLICY_DECISION = "policy_decision"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"
    ACTION_EXECUTED = "action_executed"
    INCIDENT_CREATED = "incident_created"
    INCIDENT_RESOLVED = "incident_resolved"


class ApprovalStatus(str, Enum):
    """Status of a human-in-the-loop approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ToolName(str, Enum):
    """Canonical tool names registered with the ToolBroker."""

    SCHEDULE_INSPECTION = "schedule_inspection"
    REDUCE_MACHINE_LOAD = "reduce_machine_load"
    SHUTDOWN_MACHINE = "shutdown_machine"
    GET_MACHINE_STATUS = "get_machine_status"
    GET_SENSOR_HISTORY = "get_sensor_history"
    REQUEST_HUMAN_APPROVAL = "request_human_approval"


class PolicyDecision(str, Enum):
    """Outcome of a policy evaluation for a proposed action."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class IncidentStatus(str, Enum):
    """Lifecycle status of an incident."""

    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"