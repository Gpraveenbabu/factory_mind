"""Failure signatures — the knowledge base for root-cause analysis.

A failure signature defines which sensor patterns indicate a specific failure
mode. Each signature has:
- A set of **primary sensors** (must be anomalous).
- A set of **secondary sensors** (supporting evidence).
- A set of **expected trends** (which sensors should be trending up/down).
- A set of **required correlations** (which sensor pairs should correlate).

The RCA engine matches observed anomalies against these signatures to
compute a confidence score for each possible root cause.

This is **deterministic** — the LLM does not participate in this step.
The LLM only interprets and communicates the RCA output to the operator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from factorymind.domain.enums import FailureMode


@dataclass(frozen=True)
class FailureSignature:
    """Signature of one failure mode in sensor space.

    Attributes:
        mode: The failure mode.
        primary_sensors: Sensors that MUST be anomalous for this signature.
        secondary_sensors: Sensors that provide supporting evidence.
        expected_trends: {sensor: "increasing" | "decreasing"}
        correlated_pairs: Pairs of sensors expected to move together.
        description: Human-readable description.
        min_confidence: Minimum confidence threshold for a match.
    """

    mode: FailureMode
    primary_sensors: list[str]
    secondary_sensors: list[str]
    expected_trends: dict[str, str]  # sensor -> "increasing" | "decreasing"
    correlated_pairs: list[tuple[str, str]]
    description: str
    min_confidence: float = 0.5


# --- Failure Signature Registry ---

FAILURE_SIGNATURES: dict[FailureMode, FailureSignature] = {
    FailureMode.BEARING_DEGRADATION: FailureSignature(
        mode=FailureMode.BEARING_DEGRADATION,
        primary_sensors=["vibration"],
        secondary_sensors=["temperature", "motor_current", "acoustic_level"],
        expected_trends={
            "vibration": "increasing",
            "temperature": "increasing",
            "motor_current": "increasing",
        },
        correlated_pairs=[("vibration", "temperature"), ("vibration", "motor_current")],
        description="Progressive bearing wear: vibration rises first, temperature and current follow.",
    ),
    FailureMode.BEARING_FAILURE: FailureSignature(
        mode=FailureMode.BEARING_FAILURE,
        primary_sensors=["vibration", "temperature"],
        secondary_sensors=["motor_current", "acoustic_level", "rpm"],
        expected_trends={
            "vibration": "increasing",
            "temperature": "increasing",
        },
        correlated_pairs=[("vibration", "temperature"), ("vibration", "motor_current")],
        description="Sudden bearing failure: rapid vibration and temperature spike.",
    ),
    FailureMode.THERMAL_OVERLOAD: FailureSignature(
        mode=FailureMode.THERMAL_OVERLOAD,
        primary_sensors=["temperature", "coolant_temperature"],
        secondary_sensors=["motor_current", "acoustic_level"],
        expected_trends={
            "temperature": "increasing",
            "coolant_temperature": "increasing",
            "coolant_flow": "decreasing",
        },
        correlated_pairs=[("temperature", "coolant_temperature"), ("coolant_flow", "coolant_temperature")],
        description="Thermal overload: temperature rises sigmoidally, cooling overwhelmed.",
    ),
    FailureMode.MECHANICAL_IMBALANCE: FailureSignature(
        mode=FailureMode.MECHANICAL_IMBALANCE,
        primary_sensors=["vibration"],
        secondary_sensors=["pressure", "motor_current"],
        expected_trends={
            "vibration": "increasing",
            "pressure": "increasing",
        },
        correlated_pairs=[("vibration", "pressure"), ("vibration", "motor_current")],
        description="Mechanical imbalance: vibration increases, pressure fluctuates.",
    ),
    FailureMode.MOTOR_OVERLOAD: FailureSignature(
        mode=FailureMode.MOTOR_OVERLOAD,
        primary_sensors=["motor_current"],
        secondary_sensors=["temperature", "load", "rpm"],
        expected_trends={
            "motor_current": "increasing",
            "temperature": "increasing",
            "load": "increasing",
            "rpm": "decreasing",
        },
        correlated_pairs=[("load", "motor_current"), ("motor_current", "temperature")],
        description="Motor overload: current spikes first, temperature follows, rpm drops.",
    ),
    FailureMode.COOLING_FAILURE: FailureSignature(
        mode=FailureMode.COOLING_FAILURE,
        primary_sensors=["coolant_flow", "coolant_temperature"],
        secondary_sensors=["temperature"],
        expected_trends={
            "coolant_flow": "decreasing",
            "coolant_temperature": "increasing",
            "temperature": "increasing",
        },
        correlated_pairs=[("coolant_flow", "coolant_temperature"), ("coolant_flow", "temperature")],
        description="Cooling failure: coolant flow drops, temperature cascades upward.",
    ),
    FailureMode.SENSOR_FAULT: FailureSignature(
        mode=FailureMode.SENSOR_FAULT,
        primary_sensors=[],  # special: detected by correlation anomaly
        secondary_sensors=[],
        expected_trends={},
        correlated_pairs=[],
        description="Sensor fault: one sensor deviates without correlated sensor response.",
    ),
}


def get_signature(mode: FailureMode) -> FailureSignature:
    """Return the failure signature for a mode."""
    return FAILURE_SIGNATURES[mode]


def all_signatures() -> list[FailureSignature]:
    """Return all failure signatures (excluding NONE)."""
    return [s for mode, s in FAILURE_SIGNATURES.items() if mode != FailureMode.NONE and mode != FailureMode.SENSOR_FAULT]