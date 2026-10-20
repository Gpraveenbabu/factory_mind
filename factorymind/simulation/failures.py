"""Failure mode definitions for the industrial simulator.

Each failure mode defines:
1. Which sensors it affects and in what order.
2. How deviations grow over time (temporal trajectory).
3. The degradation progression from healthy → critical.

This is the heart of why FactoryMind is NOT a random number generator.
A bearing degradation produces a **specific temporal signature** that differs
from a thermal overload or a cooling failure.

All trajectories are parameterised by ``progress`` ∈ [0, 1], where 0 = healthy
and 1 = critical failure. The growth function is non-linear to mimic real
degradation curves (exponential for bearing wear, sigmoid for thermal runaway).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from factorymind.domain.enums import FailureMode


# Type alias for the deviation function.
DeviationFn = Callable[[float], dict[str, float]]


def _linear(p: float, scale: float) -> float:
    """Linear growth: ``p * scale``."""
    return p * scale


def _exponential(p: float, scale: float, k: float = 3.0) -> float:
    """Exponential growth: mimics progressive bearing wear."""
    return scale * (np.exp(k * p) - 1) / (np.exp(k) - 1)


def _sigmoid(p: float, scale: float, k: float = 8.0) -> float:
    """Sigmoid growth: mimics thermal runaway — slow then sudden."""
    return scale / (1 + np.exp(-k * (p - 0.5))) - scale / (1 + np.exp(k * 0.5))


def _step(p: float, threshold: float, scale: float) -> float:
    """Step function: sudden onset after threshold (e.g. bearing seizure)."""
    return scale if p >= threshold else 0.0


@dataclass(frozen=True)
class FailureProfile:
    """Defines the temporal trajectory of one failure mode.

    Attributes:
        mode: The FailureMode enum value.
        affected_sensors: Sensors that deviate from nominal, in order of onset.
        deviation_fn: Function (progress) -> {sensor: deviation}.
        degradation_fn: Function (progress) -> degradation_score ∈ [0, 1].
        description: Human-readable description.
    """

    mode: FailureMode
    affected_sensors: list[str]
    deviation_fn: DeviationFn
    degradation_fn: Callable[[float], float]
    description: str


def _bearing_degradation_deviation(p: float) -> dict[str, float]:
    """Bearing wear: vibration rises first, then temperature, then current.

    Progress 0.0 → 0.3:  slight vibration increase (early detection window).
    Progress 0.3 → 0.6:  vibration accelerates, temperature begins rising.
    Progress 0.6 → 0.8:  motor current rises (extra friction load).
    Progress 0.8 → 1.0:  acoustic level spikes, rpm drops slightly.
    """
    return {
        "vibration": _exponential(p, scale=20.0, k=1.5),
        "temperature": _linear(max(0, p - 0.2), scale=20.0),
        "motor_current": _linear(max(0, p - 0.35), scale=6.0),
        "acoustic_level": _linear(max(0, p - 0.55), scale=15.0),
        "rpm": -_linear(max(0, p - 0.65), scale=50.0),  # rpm drops
    }


def _bearing_failure_deviation(p: float) -> dict[str, float]:
    """Sudden bearing failure: rapid vibration spike + temperature spike."""
    return {
        "vibration": _step(p, 0.7, 12.0) + _linear(p, 2.0),
        "temperature": _step(p, 0.75, 25.0) + _linear(p, 5.0),
        "motor_current": _step(p, 0.8, 8.0),
        "acoustic_level": _step(p, 0.8, 20.0),
        "rpm": -_step(p, 0.85, 200.0),
    }


def _thermal_overload_deviation(p: float) -> dict[str, float]:
    """Thermal overload: temperature rises sigmoidally, cooling can't keep up."""
    return {
        "temperature": _sigmoid(p, scale=30.0),
        "coolant_temperature": _linear(max(0, p - 0.2), scale=25.0),
        "coolant_flow": -_linear(max(0, p - 0.4), scale=3.0),  # flow drops
        "motor_current": _linear(max(0, p - 0.3), scale=5.0),
        "acoustic_level": _linear(max(0, p - 0.5), scale=8.0),
    }


def _mechanical_imbalance_deviation(p: float) -> dict[str, float]:
    """Mechanical imbalance: vibration oscillation increases, pressure fluctuates."""
    return {
        "vibration": _exponential(p, scale=5.0, k=2.0),
        "pressure": _linear(max(0, p - 0.2), scale=2.0),  # pressure fluctuation
        "motor_current": _linear(max(0, p - 0.3), scale=4.0),
        "rpm": -_linear(max(0, p - 0.5), scale=30.0),
    }


def _motor_overload_deviation(p: float) -> dict[str, float]:
    """Motor overload: current spikes first, then temperature, then rpm drops."""
    return {
        "motor_current": _exponential(p, scale=10.0, k=2.0),
        "temperature": _linear(max(0, p - 0.15), scale=18.0),
        "load": _linear(p, scale=25.0),
        "rpm": -_linear(max(0, p - 0.4), scale=80.0),
        "acoustic_level": _linear(max(0, p - 0.5), scale=10.0),
    }


def _cooling_failure_deviation(p: float) -> dict[str, float]:
    """Cooling failure: coolant flow drops, coolant temp rises, machine overheats."""
    return {
        "coolant_flow": -_exponential(p, scale=7.0, k=2.5),
        "coolant_temperature": _exponential(p, scale=40.0, k=2.0),
        "temperature": _linear(max(0, p - 0.2), scale=25.0),
        "motor_current": _linear(max(0, p - 0.4), scale=3.0),
    }


def _sensor_fault_deviation(p: float) -> dict[str, float]:
    """Sensor fault: one sensor reads erratically without actual machine degradation.

    This is special — it produces sensor anomalies WITHOUT real degradation.
    The RCA engine must distinguish this from real failures.
    """
    # Return zero deviation — the fault is injected at the sensor level,
    # not at the machine level. The sensor generator handles it.
    return {}


def _default_degradation(p: float) -> float:
    """Default degradation curve: maps progress [0,1] to degradation_score [0,1]."""
    return float(np.clip(p, 0.0, 1.0))


def _sensor_fault_degradation(p: float) -> float:
    """Sensor fault should NOT increase the machine degradation score."""
    return 0.0


# Registry of all failure profiles.
FAILURE_PROFILES: dict[FailureMode, FailureProfile] = {
    FailureMode.BEARING_DEGRADATION: FailureProfile(
        mode=FailureMode.BEARING_DEGRADATION,
        affected_sensors=["vibration", "temperature", "motor_current", "acoustic_level", "rpm"],
        deviation_fn=_bearing_degradation_deviation,
        degradation_fn=_default_degradation,
        description="Progressive bearing wear: vibration rises exponentially, followed by temperature and current.",
    ),
    FailureMode.BEARING_FAILURE: FailureProfile(
        mode=FailureMode.BEARING_FAILURE,
        affected_sensors=["vibration", "temperature", "motor_current", "acoustic_level", "rpm"],
        deviation_fn=_bearing_failure_deviation,
        degradation_fn=_default_degradation,
        description="Sudden bearing failure: rapid vibration spike and temperature jump.",
    ),
    FailureMode.THERMAL_OVERLOAD: FailureProfile(
        mode=FailureMode.THERMAL_OVERLOAD,
        affected_sensors=["temperature", "coolant_temperature", "coolant_flow", "motor_current", "acoustic_level"],
        deviation_fn=_thermal_overload_deviation,
        degradation_fn=_default_degradation,
        description="Thermal overload: sigmoidal temperature rise, cooling system overwhelmed.",
    ),
    FailureMode.MECHANICAL_IMBALANCE: FailureProfile(
        mode=FailureMode.MECHANICAL_IMBALANCE,
        affected_sensors=["vibration", "pressure", "motor_current", "rpm"],
        deviation_fn=_mechanical_imbalance_deviation,
        degradation_fn=_default_degradation,
        description="Mechanical imbalance: vibration increases, pressure fluctuates.",
    ),
    FailureMode.MOTOR_OVERLOAD: FailureProfile(
        mode=FailureMode.MOTOR_OVERLOAD,
        affected_sensors=["motor_current", "temperature", "load", "rpm", "acoustic_level"],
        deviation_fn=_motor_overload_deviation,
        degradation_fn=_default_degradation,
        description="Motor overload: current spikes first, temperature follows, rpm drops.",
    ),
    FailureMode.COOLING_FAILURE: FailureProfile(
        mode=FailureMode.COOLING_FAILURE,
        affected_sensors=["coolant_flow", "coolant_temperature", "temperature", "motor_current"],
        deviation_fn=_cooling_failure_deviation,
        degradation_fn=_default_degradation,
        description="Cooling failure: coolant flow drops, temperature cascades upward.",
    ),
    FailureMode.SENSOR_FAULT: FailureProfile(
        mode=FailureMode.SENSOR_FAULT,
        affected_sensors=[],
        deviation_fn=_sensor_fault_deviation,
        degradation_fn=_sensor_fault_degradation,
        description="Sensor fault: erroneous readings without real machine degradation.",
    ),
}


def get_failure_profile(mode: FailureMode) -> FailureProfile:
    """Return the failure profile for a given mode.

    Raises:
        KeyError: If the mode is not in the registry.
    """
    return FAILURE_PROFILES[mode]


def all_failure_modes() -> list[FailureMode]:
    """Return all non-NONE failure modes."""
    return [m for m in FAILURE_PROFILES if m != FailureMode.NONE]