"""Cross-sensor correlation features.

Real industrial failures produce **correlated** sensor deviations. A bearing
failure increases vibration, which increases temperature, which increases
motor current. A cooling failure decreases coolant flow, which increases
coolant temperature, which increases machine temperature.

This module computes pairwise relationships that the RCA engine uses to
distinguish real failures from single-sensor faults:

- ``temperature / vibration ratio``: should be roughly constant in healthy operation.
- ``vibration / motor_current ratio``: increases when bearing degrades (friction ↑).
- ``coolant_flow / coolant_temperature ratio``: should be stable; drops in cooling failure.
- ``load / motor_current ratio``: should be stable; drops in motor overload.

A **correlation anomaly** (one sensor deviates but its correlated partner does
not) is a strong signal of a **sensor fault**, not a machine failure.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from factorymind.domain.models import TelemetrySnapshot


@dataclass
class CorrelationState:
    """Tracks values for a pair of sensors to compute rolling correlation."""

    sensor_a: str
    sensor_b: str
    window_size: int = 10
    _values_a: deque[float] = field(init=False)
    _values_b: deque[float] = field(init=False)

    def __post_init__(self) -> None:
        self._values_a = deque(maxlen=self.window_size)
        self._values_b = deque(maxlen=self.window_size)

    def add(self, a: float, b: float) -> None:
        if a == a and b == b:  # both not NaN
            self._values_a.append(a)
            self._values_b.append(b)

    def ratio(self) -> float:
        """Current ratio a/b. Returns NaN if b is zero."""
        vals_a = list(self._values_a)
        vals_b = list(self._values_b)
        if not vals_a or not vals_b:
            return float("nan")
        b = vals_b[-1]
        if b == 0:
            return float("nan")
        return vals_a[-1] / b

    def rolling_ratio_mean(self) -> float:
        """Mean of the ratio over the window."""
        vals_a = list(self._values_a)
        vals_b = list(self._values_b)
        n = min(len(vals_a), len(vals_b))
        if n == 0:
            return float("nan")
        ratios = []
        for i in range(n):
            if vals_b[i] != 0:
                ratios.append(vals_a[i] / vals_b[i])
        if not ratios:
            return float("nan")
        return sum(ratios) / len(ratios)

    def ratio_deviation(self) -> float:
        """How far the current ratio deviates from the rolling mean ratio.

        A large deviation indicates one sensor is behaving abnormally
        relative to its expected partner — a correlation anomaly.
        """
        current = self.ratio()
        baseline = self.rolling_ratio_mean()
        if current != current or baseline != baseline or baseline == 0:
            return 0.0
        return abs(current - baseline) / abs(baseline)

    def __len__(self) -> int:
        return min(len(self._values_a), len(self._values_b))


# Canonical sensor pairs to track.
CORRELATION_PAIRS: list[tuple[str, str, str]] = [
    # (sensor_a, sensor_b, pair_name)
    ("temperature", "vibration", "temp_vibration"),
    ("vibration", "motor_current", "vibration_current"),
    ("coolant_flow", "coolant_temperature", "coolant_flow_temp"),
    ("load", "motor_current", "load_current"),
]


class CorrelationFeatureEngine:
    """Computes cross-sensor correlation features."""

    def __init__(self, window_size: int = 10) -> None:
        self._states: dict[str, CorrelationState] = {
            name: CorrelationState(a, b, window_size=window_size)
            for a, b, name in CORRELATION_PAIRS
        }

    def update(self, snapshot: TelemetrySnapshot) -> dict[str, float]:
        """Update correlation state and return features."""
        features: dict[str, float] = {}

        for a, b, pair_name in CORRELATION_PAIRS:
            state = self._states[pair_name]
            val_a = snapshot.readings.get(a, float("nan"))
            val_b = snapshot.readings.get(b, float("nan"))
            state.add(val_a, val_b)

            if len(state) < 2:
                features[f"{pair_name}_ratio"] = float("nan")
                features[f"{pair_name}_ratio_deviation"] = 0.0
                continue

            features[f"{pair_name}_ratio"] = state.ratio()
            features[f"{pair_name}_ratio_deviation"] = state.ratio_deviation()

        return features

    def get_state(self, pair_name: str) -> CorrelationState | None:
        """Return the correlation state for a named pair."""
        return self._states.get(pair_name)