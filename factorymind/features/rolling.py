"""Rolling-window feature computation.

Computes standard rolling statistics for each sensor over a time window:
- rolling_mean, rolling_std, rolling_min, rolling_max
- EWMA (exponentially weighted moving average)
- lag features (value at t-k)

These features capture the **local temporal context** that a single-point
anomaly detector would miss. A vibration reading of 5.0 mm/s is normal if the
rolling mean is 4.8, but anomalous if the rolling mean is 2.5.

The implementation uses simple Python (no pandas dependency at this layer) to
keep the domain logic lightweight and testable. Pandas integration comes in
the batch processing scripts.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from factorymind.domain.models import TelemetrySnapshot


@dataclass
class RollingWindow:
    """A rolling window of scalar values for one sensor.

    Maintains a fixed-size deque and computes statistics incrementally.
    """

    sensor_name: str
    window_size: int = 10
    _values: deque[float] = field(init=False)
    _ewma: float = 0.0
    _ewma_initialized: bool = False
    _alpha: float = 0.3  # EWMA smoothing factor

    def __post_init__(self) -> None:
        self._values = deque(maxlen=self.window_size)

    def add(self, value: float) -> None:
        """Add a new value to the window."""
        if value != value:  # NaN — skip
            return
        self._values.append(value)
        if not self._ewma_initialized:
            self._ewma = value
            self._ewma_initialized = True
        else:
            self._ewma = self._alpha * value + (1 - self._alpha) * self._ewma

    def mean(self) -> float:
        """Rolling mean. Returns NaN if window is empty."""
        if not self._values:
            return float("nan")
        return sum(self._values) / len(self._values)

    def std(self) -> float:
        """Rolling standard deviation (population)."""
        if len(self._values) < 2:
            return 0.0
        m = self.mean()
        var = sum((v - m) ** 2 for v in self._values) / len(self._values)
        return math.sqrt(var)

    def min_val(self) -> float:
        if not self._values:
            return float("nan")
        return min(self._values)

    def max_val(self) -> float:
        if not self._values:
            return float("nan")
        return max(self._values)

    def ewma(self) -> float:
        return self._ewma if self._ewma_initialized else float("nan")

    def lag(self, k: int) -> float:
        """Return the value ``k`` steps ago. Returns NaN if not enough data."""
        vals = list(self._values)
        if k >= len(vals):
            return float("nan")
        return vals[-(k + 1)]

    def __len__(self) -> int:
        return len(self._values)


class RollingFeatureEngine:
    """Computes rolling features for all sensors of one machine.

    Maintains a ``RollingWindow`` per sensor and produces a feature dict
    at each step.
    """

    def __init__(self, sensor_names: list[str], window_size: int = 10) -> None:
        self._windows: dict[str, RollingWindow] = {
            name: RollingWindow(sensor_name=name, window_size=window_size)
            for name in sensor_names
        }

    def update(self, snapshot: TelemetrySnapshot) -> dict[str, float]:
        """Update all rolling windows and return the feature vector."""
        features: dict[str, float] = {}

        for name, window in self._windows.items():
            value = snapshot.readings.get(name, float("nan"))
            window.add(value)

            if len(window) == 0:
                continue

            # Rolling statistics
            features[f"{name}_rolling_mean"] = window.mean()
            features[f"{name}_rolling_std"] = window.std()
            features[f"{name}_rolling_min"] = window.min_val()
            features[f"{name}_rolling_max"] = window.max_val()
            features[f"{name}_ewma"] = window.ewma()

            # Lag features (1-step and 5-step)
            features[f"{name}_lag_1"] = window.lag(1)
            features[f"{name}_lag_5"] = window.lag(5)

        return features