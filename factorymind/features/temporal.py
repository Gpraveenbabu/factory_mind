"""Temporal trend features — slope, rate of change, trend direction.

These features capture **how fast** sensor values are changing, not just their
current level. This is critical for distinguishing:
- A temporary vibration spike (high value, zero slope → transient)
- Progressive bearing failure (moderate value, positive slope → trending)

The slope is computed via least-squares linear regression over the rolling
window, which is more robust than simple differencing.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from factorymind.domain.models import TelemetrySnapshot


@dataclass
class TrendState:
    """Per-sensor state for trend computation."""

    sensor_name: str
    window_size: int = 10
    _values: deque[float] = field(init=False)

    def __post_init__(self) -> None:
        self._values = deque(maxlen=self.window_size)

    def add(self, value: float) -> None:
        if value == value:  # not NaN
            self._values.append(value)

    def slope(self) -> float:
        """Compute linear regression slope (least squares).

        Returns the rate of change per step. A positive slope means the
        sensor value is increasing over the window.
        """
        vals = list(self._values)
        n = len(vals)
        if n < 2:
            return 0.0

        x_mean = (n - 1) / 2.0
        y_mean = sum(vals) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(vals))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def rate_of_change(self) -> float:
        """Simple rate of change: (current - oldest) / window_size."""
        vals = list(self._values)
        if len(vals) < 2:
            return 0.0
        return (vals[-1] - vals[0]) / len(vals)

    def trend_direction(self) -> str:
        """Categorical trend: 'increasing', 'decreasing', 'stable'."""
        s = self.slope()
        # Threshold: relative to the mean value
        vals = list(self._values)
        if not vals or len(vals) < 2:
            return "stable"
        mean_val = sum(abs(v) for v in vals) / len(vals)
        if mean_val == 0:
            return "stable"
        relative_slope = abs(s) / mean_val
        if relative_slope < 0.005:
            return "stable"
        return "increasing" if s > 0 else "decreasing"

    def is_trending(self, min_relative_slope: float = 0.02) -> bool:
        """Return True if the sensor shows a statistically meaningful trend."""
        s = self.slope()
        vals = list(self._values)
        if not vals or len(vals) < 2:
            return False
        mean_val = sum(abs(v) for v in vals) / len(vals)
        if mean_val == 0:
            return False
        return abs(s) / mean_val >= min_relative_slope

    def __len__(self) -> int:
        return len(self._values)


class TemporalFeatureEngine:
    """Computes temporal trend features for all sensors of one machine."""

    def __init__(self, sensor_names: list[str], window_size: int = 10) -> None:
        self._states: dict[str, TrendState] = {
            name: TrendState(sensor_name=name, window_size=window_size)
            for name in sensor_names
        }

    def update(self, snapshot: TelemetrySnapshot) -> dict[str, float | str]:
        """Update trend state and return temporal features."""
        features: dict[str, float | str] = {}

        for name, state in self._states.items():
            value = snapshot.readings.get(name, float("nan"))
            state.add(value)

            if len(state) < 2:
                features[f"{name}_slope"] = 0.0
                features[f"{name}_rate_of_change"] = 0.0
                features[f"{name}_trend"] = "stable"
                continue

            features[f"{name}_slope"] = state.slope()
            features[f"{name}_rate_of_change"] = state.rate_of_change()
            features[f"{name}_trend"] = state.trend_direction()

        return features

    def get_trend_state(self, sensor_name: str) -> TrendState | None:
        """Return the TrendState for a sensor (for direct inspection)."""
        return self._states.get(sensor_name)