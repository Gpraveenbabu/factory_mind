"""Root Cause Analysis engine.

The RCA engine is **deterministic**. It:
1. Collects evidence (thresholds, trends, correlations, contradictions).
2. Matches evidence against failure signatures.
3. Computes a confidence score for each candidate root cause.
4. Selects the best match and returns a ``RootCauseResult``.

Confidence scoring:
- Each primary sensor that is anomalous contributes +0.3.
- Each secondary sensor that is anomalous contributes +0.15.
- Each matching trend contributes +0.1.
- Each matching correlation contributes +0.1.
- Each contradiction reduces confidence by 0.2.
- Scores are clamped to [0, 1].

The engine also handles the special SENSOR_FAULT case: if one sensor is
anomalous but its correlated partners show no response, the engine identifies
sensor_fault rather than a machine failure.
"""

from __future__ import annotations

from datetime import datetime

from factorymind.domain.enums import FailureMode, HealthState
from factorymind.domain.models import RootCauseResult, TelemetrySnapshot
from factorymind.rca.evidence import EvidenceBundle, EvidenceCollector
from factorymind.rca.signatures import FailureSignature, all_signatures, get_signature
from factorymind.simulation.sensors import ALL_SENSORS


class RCAEngine:
    """Deterministic root-cause analysis engine.

    Args:
        sensor_names: List of sensor names to track.
        window_size: Feature window size.
    """

    def __init__(self, sensor_names: list[str] | None = None, window_size: int = 10) -> None:
        self._sensor_names = sensor_names or list(ALL_SENSORS)
        self._collector = EvidenceCollector(self._sensor_names, window_size)

    def analyze(
        self,
        snapshot: TelemetrySnapshot,
        anomalies: list,  # list[Anomaly]
        degradation_score: float = 0.0,
    ) -> RootCauseResult:
        """Analyze the current state and return the root cause.

        Args:
            snapshot: Latest telemetry snapshot.
            anomalies: Anomalies detected at this step.
            degradation_score: Current degradation score from the simulator.

        Returns:
            RootCauseResult with the identified root cause and evidence.
        """
        bundle = self._collector.collect(snapshot, anomalies)

        # If no anomalies → healthy (trends without threshold breaches are noise)
        if not bundle.has_anomalies:
            return RootCauseResult(
                machine_id=snapshot.machine_id,
                timestamp=snapshot.timestamp,
                root_cause=FailureMode.NONE,
                confidence=1.0,
                evidence=bundle.evidence_items,
                health_state=_health_from_score(degradation_score),
                degradation_score=degradation_score,
            )

        # --- Check for sensor fault first ---
        if self._is_sensor_fault(bundle):
            return RootCauseResult(
                machine_id=snapshot.machine_id,
                timestamp=snapshot.timestamp,
                root_cause=FailureMode.SENSOR_FAULT,
                confidence=0.85,
                evidence=bundle.evidence_items,
                health_state=_health_from_score(degradation_score),
                degradation_score=degradation_score,
            )

        # --- Match against failure signatures ---
        best_mode = FailureMode.NONE
        best_confidence = 0.0
        best_evidence = bundle.evidence_items

        for sig in all_signatures():
            confidence, matched_evidence = self._match_signature(sig, bundle)
            if confidence > best_confidence:
                best_confidence = confidence
                best_mode = sig.mode
                best_evidence = matched_evidence

        return RootCauseResult(
            machine_id=snapshot.machine_id,
            timestamp=snapshot.timestamp,
            root_cause=best_mode if best_confidence >= 0.3 else FailureMode.NONE,
            confidence=best_confidence,
            evidence=best_evidence,
            health_state=_health_from_score(degradation_score),
            degradation_score=degradation_score,
        )

    def _is_sensor_fault(self, bundle: EvidenceBundle) -> bool:
        """Check if evidence points to a sensor fault rather than a machine failure.

        A sensor fault is indicated by:
        - One or few anomalous sensors.
        - Contradiction pairs present (anomalous sensor with normal partner).
        - The anomalous sensor does NOT have a consistent trend (sensor faults
          produce erratic readings, not a steadily increasing/decreasing signal).
        - No broad trend across multiple sensors.

        If the anomalous sensor IS trending consistently (e.g., vibration is
        steadily increasing), this is more likely a real developing failure,
        not a sensor fault -- even if correlated partners have not responded yet.
        """
        if len(bundle.contradiction_pairs) == 0:
            return False

        # If only 1-2 sensors are anomalous and there are contradictions,
        # and no broad multi-sensor trend, it might be a sensor fault.
        if len(bundle.anomalous_sensors) <= 2:
            trending_count = sum(1 for t in bundle.trends.values() if t != "stable")
            if trending_count <= 2:
                # Key check: if any anomalous sensor has a consistent trend
                # (increasing or decreasing), it is likely a real developing
                # failure, not a sensor fault. Sensor faults produce erratic
                # readings without a consistent directional trend.
                for sensor in bundle.anomalous_sensors:
                    trend = bundle.trends.get(sensor, "stable")
                    if trend != "stable":
                        return False
                return True

        return False

    def _match_signature(
        self,
        sig: FailureSignature,
        bundle: EvidenceBundle,
    ) -> tuple[float, list]:
        """Match evidence against a failure signature.

        Returns (confidence, evidence_items).
        """
        confidence = 0.0
        matched_evidence: list = list(bundle.evidence_items)

        # --- Primary sensor check ---
        primary_hits = sum(
            1 for s in sig.primary_sensors if s in bundle.anomalous_sensors
        )
        if sig.primary_sensors:
            primary_ratio = primary_hits / len(sig.primary_sensors)
            confidence += primary_ratio * 0.3

            # If no primary sensors are anomalous, this signature is unlikely.
            if primary_hits == 0:
                return 0.0, matched_evidence

        # --- Secondary sensor check ---
        secondary_hits = sum(
            1 for s in sig.secondary_sensors if s in bundle.anomalous_sensors
        )
        if sig.secondary_sensors:
            confidence += (secondary_hits / len(sig.secondary_sensors)) * 0.15

        # --- Trend matching ---
        for sensor, expected_trend in sig.expected_trends.items():
            actual_trend = bundle.trends.get(sensor, "stable")
            if actual_trend == expected_trend:
                confidence += 0.1
                matched_evidence.append(_make_evidence(
                    source=f"{sensor}_trend_match",
                    description=f"{sensor} trend matches expected '{expected_trend}' for {sig.mode.value}",
                    weight=0.1,
                ))

        # --- Contradiction penalty ---
        for sensor, partner in bundle.contradiction_pairs:
            # If the contradiction involves a primary sensor, it reduces confidence.
            if sensor in sig.primary_sensors or partner in sig.primary_sensors:
                confidence -= 0.2

        # --- Clamp ---
        confidence = max(0.0, min(1.0, confidence))

        return confidence, matched_evidence


def _health_from_score(score: float) -> HealthState:
    """Map degradation score to HealthState."""
    if score < 0.2:
        return HealthState.HEALTHY
    if score < 0.5:
        return HealthState.EARLY_DEGRADATION
    if score < 0.75:
        return HealthState.DEVELOPING_FAULT
    if score < 0.95:
        return HealthState.SEVERE_DEGRADATION
    return HealthState.CRITICAL_FAILURE


def _make_evidence(source: str, description: str, weight: float = 1.0):
    """Helper to create an EvidenceItem."""
    from factorymind.domain.models import EvidenceItem
    return EvidenceItem(
        source=source,
        description=description,
        weight=weight,
    )