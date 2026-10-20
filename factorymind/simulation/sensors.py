"""Sensor definitions and generation logic for the industrial simulator.

Each sensor has a nominal operating range, a noise model, and a set of failure
interaction factors. The ``SensorSpec`` dataclass captures these, and the
``SensorGenerator`` produces correlated readings step-by-step.

Design notes:
- Sensors are **correlated** by physics, not independent noise.
- Temperature ↔ vibration ↔ motor_current form a thermal-mechanical chain.
- Coolant_flow ↔ coolant_temperature form a thermal management loop.
- Load drives motor_current, which drives temperature, which drives cooling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from factorymind.domain.enums import ALL_SENSORS  # re-export for convenience


class NoiseModel(Protocol):
    """Protocol for noise injection strategies."""

    def sample(self, rng: np.random.Generator) -> float:
        ...


@dataclass(frozen=True)
class GaussianNoise:
    """Simple additive Gaussian noise."""

    std: float = 0.5

    def sample(self, rng: np.random.Generator) -> float:
        return float(rng.normal(0.0, self.std))


@dataclass(frozen=True)
class SensorSpec:
    """Static specification of one sensor.

    Attributes:
        name: Canonical sensor identifier.
        nominal_mean: Value in healthy operation.
        nominal_std: Natural variability when healthy.
        min_value: Physical minimum (for clamping).
        max_value: Physical maximum (for clamping).
        unit: Engineering unit for display.
    """

    name: str
    nominal_mean: float
    nominal_std: float
    min_value: float
    max_value: float
    unit: str


# Default sensor specifications for the FM-2000 machine model.
DEFAULT_SENSOR_SPECS: dict[str, SensorSpec] = {
    "temperature": SensorSpec("temperature", 75.0, 2.0, 0.0, 200.0, "°C"),
    "vibration": SensorSpec("vibration", 2.5, 0.3, 0.0, 20.0, "mm/s"),
    "pressure": SensorSpec("pressure", 5.2, 0.15, 0.0, 15.0, "bar"),
    "motor_current": SensorSpec("motor_current", 11.0, 0.5, 0.0, 30.0, "A"),
    "rpm": SensorSpec("rpm", 1500.0, 5.0, 0.0, 3000.0, "rpm"),
    "load": SensorSpec("load", 55.0, 3.0, 0.0, 100.0, "%"),
    "coolant_temperature": SensorSpec("coolant_temperature", 30.0, 1.0, 0.0, 100.0, "°C"),
    "coolant_flow": SensorSpec("coolant_flow", 10.0, 0.3, 0.0, 30.0, "L/min"),
    "acoustic_level": SensorSpec("acoustic_level", 72.0, 2.0, 0.0, 130.0, "dB"),
}


def get_sensor_specs() -> dict[str, SensorSpec]:
    """Return a fresh copy of the default sensor specifications."""
    return dict(DEFAULT_SENSOR_SPECS)


@dataclass
class SensorQualityConfig:
    """Configuration for sensor data quality issues.

    These are probabilities per step per sensor. They simulate real-world
    problems: drift, dropout, stuck values, outliers, missing values.
    """

    drift_rate: float = 0.0       # additive bias per step
    dropout_prob: float = 0.0     # probability of NaN reading
    stuck_prob: float = 0.0       # probability of repeating last value
    outlier_prob: float = 0.0     # probability of extreme value
    outlier_factor: float = 5.0  # multiplier for outlier magnitude


@dataclass
class SensorState:
    """Mutable per-sensor state tracked across simulation steps."""

    last_value: float = 0.0
    stuck: bool = False
    drift_bias: float = 0.0


class SensorGenerator:
    """Generates correlated sensor readings step-by-step.

    The generator maintains internal state for drift and stuck-value tracking.
    It applies physics-based correlations and data-quality faults.

    Parameters:
        specs: Sensor specifications.
        seed: Random seed for reproducibility.
        noise_std: Base noise standard deviation (multiplied by sensor nominal_std).
        quality: Data-quality configuration.
    """

    def __init__(
        self,
        specs: dict[str, SensorSpec] | None = None,
        seed: int = 42,
        noise_std: float = 0.5,
        quality: SensorQualityConfig | None = None,
    ) -> None:
        self.specs = specs or get_sensor_specs()
        self._rng = np.random.default_rng(seed)
        self.noise_std = noise_std
        self.quality = quality or SensorQualityConfig()
        self._states: dict[str, SensorState] = {
            name: SensorState(last_value=spec.nominal_mean)
            for name, spec in self.specs.items()
        }

    def step(
        self,
        deviations: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Generate one set of sensor readings.

        Args:
            deviations: Per-sensor deviation from nominal (applied by failure models).
                         e.g. {"vibration": +1.5, "temperature": +10.0}

        Returns:
            Dict mapping sensor_name to value. Missing readings are NaN.
        """
        deviations = deviations or {}
        readings: dict[str, float] = {}

        for name, spec in self.specs.items():
            state = self._states[name]

            # --- Stuck value: repeat last reading ---
            if state.stuck:
                readings[name] = state.last_value
                continue

            # --- Compute base value ---
            base = spec.nominal_mean + deviations.get(name, 0.0)
            noise = float(self._rng.normal(0.0, spec.nominal_std * self.noise_std))
            value = base + noise + state.drift_bias

            # --- Outlier injection ---
            if self.quality.outlier_prob > 0 and self._rng.random() < self.quality.outlier_prob:
                value += float(self._rng.normal(0, spec.nominal_std * self.quality.outlier_factor))

            # --- Dropout: produce NaN ---
            if self.quality.dropout_prob > 0 and self._rng.random() < self.quality.dropout_prob:
                readings[name] = float("nan")
                continue

            # --- Stuck value onset ---
            if self.quality.stuck_prob > 0 and self._rng.random() < self.quality.stuck_prob:
                state.stuck = True
                readings[name] = state.last_value
                continue

            # --- Apply drift ---
            if self.quality.drift_rate > 0:
                state.drift_bias += self.quality.drift_rate

            # --- Clamp to physical range ---
            value = float(np.clip(value, spec.min_value, spec.max_value))

            readings[name] = value
            state.last_value = value

        return readings

    def reset(self, seed: int | None = None) -> None:
        """Reset generator state (useful for re-running scenarios)."""
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._states = {
            name: SensorState(last_value=spec.nominal_mean)
            for name, spec in self.specs.items()
        }