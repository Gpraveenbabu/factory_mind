"""Rule-based anomaly detector.

This is the baseline detector. It uses fixed thresholds derived from the
sensor specifications and config. Despite its simplicity, a well-tuned rule
detector is a strong baseline because it encodes domain knowledge directly.

The detector produces ``Anomaly`` objects with severity scores. It also uses
the rolling mean to avoid false positives from single noisy readings — a
reading triggers an anomaly only if it **and** its rolling mean exceed the
threshold.

Phase 2 will add Isolation Forest and Autoencoder detectors, which will be
compared against this baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from factorymind.domain.enums import AnomalyType
from factorymind.domain.models import Anomaly, FeatureVector, TelemetrySnapshot
from factorymind.features.rolling import RollingFeatureEngine
from factorymind.features.temporal import TemporalFeatureEngine


@dataclass(frozen=True)
class ThresholdConfig:
    """Threshold configuration for the rule-based detector.

    Each sensor has a ``warn`` and ``critical`` threshold. A reading above
    ``warn`` produces a warning anomaly; above ``critical`` produces a critical
    anomaly. For sensors where low values are bad (e.g. pressure, coolant_flow),
    the thresholds represent minimums.
    """

    temperature_warn: float = 90.0
    temperature_critical: float = 100.0
    vibration_warn: float = 5.5
    vibration_critical: float = 8.0
    motor_current_warn: float = 16.0
    motor_current_critical: float = 20.0
    coolant_temp_warn: float = 40.0
    coolant_temp_critical: float = 50.0
    coolant_flow_low_warn: float = 7.0
    coolant_flow_low_critical: float = 5.0
    pressure_low_warn: float = 3.5
    pressure_low_critical: float = 2.5
    acoustic_warn: float = 85.0
    acoustic_critical: float = 95.0


# Sensors where low values are the anomaly (not high).
LOW_IS_BAD_SENSORS = {"pressure", "coolant_flow"}


class RuleDetector:
    """Rule-based anomaly detector using fixed thresholds.

    The detector maintains rolling and temporal feature engines internally.
    Each call to ``detect`` updates the features and checks thresholds.

    Args:
        thresholds: Threshold configuration.
        window_size: Rolling window size for feature computation.
        require_trend_confirmation: If True, a threshold breach must be
            confirmed by a positive trend to be flagged (reduces false positives
            from transient spikes).
    """

    def __init__(
        self,
        thresholds: ThresholdConfig | None = None,
        window_size: int = 10,
        require_trend_confirmation: bool = False,
    ) -> None:
        self.thresholds = thresholds or ThresholdConfig()
        self._rolling: dict[str, RollingFeatureEngine] = {}
        self._temporal: dict[str, TemporalFeatureEngine] = {}
        self._window_size = window_size
        self._require_trend = require_trend_confirmation
        self._sensor_names = list(ThresholdConfig.__dataclass_fields__.keys())

    def _ensure_engines(self, machine_id: str, sensor_names: list[str]) -> None:
        if machine_id not in self._rolling:
            self._rolling[machine_id] = RollingFeatureEngine(sensor_names, self._window_size)
            self._temporal[machine_id] = TemporalFeatureEngine(sensor_names, self._window_size)

    def detect(self, snapshot: TelemetrySnapshot) -> list[Anomaly]:
        """Detect anomalies in a telemetry snapshot.

        Returns a list of ``Anomaly`` objects (empty if no anomalies found).
        """
        machine_id = snapshot.machine_id
        sensor_names = list(snapshot.readings.keys())
        self._ensure_engines(machine_id, sensor_names)

        rolling_features = self._rolling[machine_id].update(snapshot)
        temporal_features = self._temporal[machine_id].update(snapshot)

        anomalies: list[Anomaly] = []

        # Check each sensor against its thresholds.
        checks = self._get_threshold_checks()

        for sensor_name, value in snapshot.readings.items():
            if value != value:  # NaN
                continue

            if sensor_name not in checks:
                continue

            warn_threshold, critical_threshold, low_is_bad = checks[sensor_name]

            # Determine if breached
            if low_is_bad:
                breached_warn = value < warn_threshold
                breached_critical = value < critical_threshold
            else:
                breached_warn = value > warn_threshold
                breached_critical = value > critical_threshold

            if not breached_warn and not breached_critical:
                continue

            # Trend confirmation: skip if trend is not in the right direction.
            if self._require_trend:
                trend = temporal_features.get(f"{sensor_name}_trend", "stable")
                if low_is_bad and trend != "decreasing":
                    continue
                if not low_is_bad and trend != "increasing":
                    continue

            # Compute severity
            if breached_critical:
                severity = 0.9
                threshold = critical_threshold
            else:
                severity = 0.5
                threshold = warn_threshold

            anomaly_type = AnomalyType.THRESHOLD_BREACH

            # Check if this is also a trend anomaly
            slope = temporal_features.get(f"{sensor_name}_slope", 0.0)
            if isinstance(slope, (int, float)) and abs(slope) > 0.1:
                anomaly_type = AnomalyType.TREND_ANOMALY

            anomalies.append(Anomaly(
                machine_id=machine_id,
                timestamp=snapshot.timestamp,
                sensor_name=sensor_name,
                anomaly_type=anomaly_type,
                severity=severity,
                value=value,
                threshold=threshold,
                message=f"{sensor_name}={'high' if not low_is_bad else 'low'}: {value:.2f} (threshold: {threshold:.2f})",
                detector_name="rule_detector",
            ))

        return anomalies

    def _get_threshold_checks(self) -> dict[str, tuple[float, float, bool]]:
        """Return threshold tuples for each sensor: (warn, critical, low_is_bad)."""
        t = self.thresholds
        return {
            "temperature": (t.temperature_warn, t.temperature_critical, False),
            "vibration": (t.vibration_warn, t.vibration_critical, False),
            "motor_current": (t.motor_current_warn, t.motor_current_critical, False),
            "coolant_temperature": (t.coolant_temp_warn, t.coolant_temp_critical, False),
            "coolant_flow": (t.coolant_flow_low_warn, t.coolant_flow_low_critical, True),
            "pressure": (t.pressure_low_warn, t.pressure_low_critical, True),
            "acoustic_level": (t.acoustic_warn, t.acoustic_critical, False),
        }