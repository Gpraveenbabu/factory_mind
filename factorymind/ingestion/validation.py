"""Telemetry validation — checks data quality before processing.

The validator runs a series of checks on incoming ``TelemetrySnapshot`` objects:
1. Schema check: all expected sensors are present.
2. Range check: values fall within physically plausible ranges.
3. Plausibility check: no contradictory readings (e.g. high temp + low coolant temp
   without cooling failure).
4. Completeness check: fraction of NaN readings.

Invalid readings are flagged but NOT silently dropped. The downstream pipeline
decides whether to process, impute, or reject.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from factorymind.domain.models import TelemetrySnapshot
from factorymind.simulation.sensors import DEFAULT_SENSOR_SPECS


class ValidationError(Exception):
    """Raised when a reading fails critical validation."""


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating one telemetry snapshot."""

    valid: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    missing_sensors: list[str] = field(default_factory=list)
    out_of_range: dict[str, str] = field(default_factory=dict)  # sensor -> "value (min, max)"
    nan_fraction: float = 0.0


class Validator(Protocol):
    """Protocol for telemetry validators."""

    def validate(self, snapshot: TelemetrySnapshot) -> ValidationResult:
        ...


class TelemetryValidator:
    """Validates telemetry snapshots against sensor specs and plausibility rules."""

    def __init__(
        self,
        nan_threshold: float = 0.5,
    ) -> None:
        self.nan_threshold = nan_threshold
        self._specs = DEFAULT_SENSOR_SPECS

    def validate(self, snapshot: TelemetrySnapshot) -> ValidationResult:
        """Validate a single telemetry snapshot."""
        warnings: list[str] = []
        errors: list[str] = []
        missing: list[str] = []
        out_of_range: dict[str, str] = {}

        # --- Check 1: All expected sensors present ---
        for expected in self._specs:
            if expected not in snapshot.readings:
                missing.append(expected)

        if missing:
            errors.append(f"Missing sensors: {missing}")

        # --- Check 2: Range validation ---
        for name, spec in self._specs.items():
            if name not in snapshot.readings:
                continue
            value = snapshot.readings[name]
            if value != value:  # NaN check
                continue
            if value < spec.min_value or value > spec.max_value:
                out_of_range[name] = f"{value:.2f} ({spec.min_value}, {spec.max_value})"
                warnings.append(
                    f"{name}={value:.2f} outside range [{spec.min_value}, {spec.max_value}]"
                )

        # --- Check 3: NaN fraction ---
        total = len(snapshot.readings)
        nan_count = sum(1 for v in snapshot.readings.values() if v != v)
        nan_fraction = nan_count / total if total > 0 else 0.0

        if nan_fraction > self.nan_threshold:
            errors.append(f"NaN fraction {nan_fraction:.2f} exceeds threshold {self.nan_threshold}")
        elif nan_fraction > 0:
            warnings.append(f"{nan_count}/{total} readings are NaN (fraction={nan_fraction:.2f})")

        # --- Check 4: Plausibility — contradictory readings ---
        temp = snapshot.readings.get("temperature")
        coolant_temp = snapshot.readings.get("coolant_temperature")
        if (
            temp is not None
            and coolant_temp is not None
            and temp == temp
            and coolant_temp == coolant_temp
            and temp > 120.0
            and coolant_temp < 40.0
        ):
            warnings.append(
                "Contradictory readings: high temperature with low coolant temperature "
                "(possible cooling failure or sensor fault)"
            )

        valid = len(errors) == 0
        return ValidationResult(
            valid=valid,
            warnings=warnings,
            errors=errors,
            missing_sensors=missing,
            out_of_range=out_of_range,
            nan_fraction=nan_fraction,
        )