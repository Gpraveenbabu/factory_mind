"""Evidence collection for root-cause analysis.

The evidence collector gathers all available signals that the RCA engine
uses to match failure signatures:
1. Threshold breach anomalies (from the detector).
2. Trend evidence (increasing/decreasing/stable).
3. Correlation evidence (expected pairs moving together or not).
4. Cross-sensor contradiction (one sensor anomalous, partner normal).

The output is a structured ``EvidenceBundle`` that the RCA engine consumes.
This keeps evidence collection separate from the matching logic — single
responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from factorymind.domain.models import Anomaly, EvidenceItem, TelemetrySnapshot
from factorymind.features.correlations import CorrelationFeatureEngine
from factorymind.features.temporal import TemporalFeatureEngine


@dataclass
class EvidenceBundle:
    """All evidence collected for one RCA evaluation."""

    anomalies: list[Anomaly] = field(default_factory=list)
    trends: dict[str, str] = field(default_factory=dict)  # sensor -> "increasing" | "decreasing" | "stable"
    slopes: dict[str, float] = field(default_factory=dict)  # sensor -> slope value
    correlation_deviations: dict[str, float] = field(default_factory=dict)  # pair_name -> deviation
    anomalous_sensors: set[str] = field(default_factory=set)
    contradiction_pairs: list[tuple[str, str]] = field(default_factory=list)  # (anomalous_sensor, normal_partner)
    evidence_items: list[EvidenceItem] = field(default_factory=list)

    def add_evidence(self, item: EvidenceItem) -> None:
        """Add an evidence item."""
        self.evidence_items.append(item)

    @property
    def has_anomalies(self) -> bool:
        return len(self.anomalies) > 0

    @property
    def has_trends(self) -> bool:
        return any(t != "stable" for t in self.trends.values())


class EvidenceCollector:
    """Collects evidence from telemetry, anomalies, and features.

    The collector maintains temporal and correlation feature engines per
    machine. Each call to ``collect`` updates the features and gathers all
    evidence.
    """

    def __init__(self, sensor_names: list[str], window_size: int = 10) -> None:
        self._temporal: dict[str, TemporalFeatureEngine] = {}
        self._correlation: dict[str, CorrelationFeatureEngine] = {}
        self._sensor_names = sensor_names
        self._window_size = window_size

    def _ensure_engines(self, machine_id: str) -> None:
        if machine_id not in self._temporal:
            self._temporal[machine_id] = TemporalFeatureEngine(self._sensor_names, self._window_size)
            self._correlation[machine_id] = CorrelationFeatureEngine(self._window_size)

    def collect(
        self,
        snapshot: TelemetrySnapshot,
        anomalies: list[Anomaly],
    ) -> EvidenceBundle:
        """Collect all evidence for the current step.

        Args:
            snapshot: The latest telemetry snapshot.
            anomalies: Anomalies detected at this step.

        Returns:
            An EvidenceBundle with all collected evidence.
        """
        machine_id = snapshot.machine_id
        self._ensure_engines(machine_id)

        temporal_features = self._temporal[machine_id].update(snapshot)
        correlation_features = self._correlation[machine_id].update(snapshot)

        bundle = EvidenceBundle(anomalies=list(anomalies))

        # --- Anomalous sensors ---
        bundle.anomalous_sensors = {a.sensor_name for a in anomalies}

        # --- Threshold evidence ---
        for anomaly in anomalies:
            bundle.add_evidence(EvidenceItem(
                source=f"{anomaly.sensor_name}_threshold",
                description=anomaly.message,
                value=anomaly.value,
                expected=anomaly.threshold,
                weight=anomaly.severity,
            ))

        # --- Trend evidence ---
        for sensor_name in self._sensor_names:
            trend = temporal_features.get(f"{sensor_name}_trend", "stable")
            slope = temporal_features.get(f"{sensor_name}_slope", 0.0)
            bundle.trends[sensor_name] = trend
            bundle.slopes[sensor_name] = slope if isinstance(slope, (int, float)) else 0.0

            if trend != "stable":
                bundle.add_evidence(EvidenceItem(
                    source=f"{sensor_name}_trend",
                    description=f"{sensor_name} trend: {trend} (slope={slope:.4f})",
                    value=slope if isinstance(slope, (int, float)) else 0.0,
                    expected=0.0,
                    weight=0.6,
                ))

        # --- Correlation evidence ---
        for pair_name, deviation in correlation_features.items():
            if not isinstance(deviation, (int, float)) or deviation != deviation:
                continue
            if "ratio_deviation" in pair_name:
                bundle.correlation_deviations[pair_name] = deviation
                if deviation > 0.3:
                    bundle.add_evidence(EvidenceItem(
                        source=f"{pair_name}_correlation",
                        description=f"Correlation anomaly: {pair_name} ratio deviation = {deviation:.2f}",
                        value=deviation,
                        expected=0.0,
                        weight=0.7,
                    ))

        # --- Contradiction detection: one sensor anomalous, partner normal ---
        # If vibration is anomalous but motor_current is normal → possible sensor fault.
        # If coolant_flow is anomalous but coolant_temperature is normal → possible sensor fault.
        contradiction_checks = [
            ("vibration", "motor_current"),
            ("vibration", "temperature"),
            ("coolant_flow", "coolant_temperature"),
            ("temperature", "coolant_temperature"),
        ]
        for sensor, partner in contradiction_checks:
            if sensor in bundle.anomalous_sensors and partner not in bundle.anomalous_sensors:
                # Only flag contradiction if partner should also be anomalous
                # (i.e. the sensor has a meaningful trend)
                partner_trend = bundle.trends.get(partner, "stable")
                if partner_trend == "stable":
                    bundle.contradiction_pairs.append((sensor, partner))
                    bundle.add_evidence(EvidenceItem(
                        source=f"{sensor}_{partner}_contradiction",
                        description=(
                            f"Contradiction: {sensor} is anomalous but {partner} "
                            f"shows no correlated response — possible sensor fault"
                        ),
                        weight=0.8,
                    ))

        return bundle