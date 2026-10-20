"""Tests for the rule-based anomaly detector."""

from __future__ import annotations

import pytest

from factorymind.detection.rules import RuleDetector, ThresholdConfig
from factorymind.domain.enums import AnomalyType
from factorymind.simulation.machine import MachineSimulator
from factorymind.domain.models import MachineConfig
from factorymind.domain.enums import FailureMode


class TestRuleDetector:
    def test_no_anomalies_on_healthy_machine(self, healthy_machine):
        detector = RuleDetector()
        anomalies = []
        for _ in range(50):
            snap = healthy_machine.step()
            anomalies.extend(detector.detect(snap))
        # Healthy machine should produce few or no anomalies
        assert len(anomalies) == 0, f"Expected no anomalies on healthy machine, got {len(anomalies)}"

    def test_detects_high_vibration(self, bearing_degradation_machine):
        detector = RuleDetector()
        sim = bearing_degradation_machine
        anomalies = []
        for _ in range(200):
            snap = sim.step()
            anomalies.extend(detector.detect(snap))
        # Should detect vibration anomaly
        vibration_anomalies = [a for a in anomalies if a.sensor_name == "vibration"]
        assert len(vibration_anomalies) > 0, "Should detect vibration anomaly"

    def test_detects_high_temperature(self):
        sim = MachineSimulator(MachineConfig(machine_id="M-TH"), seed=42)
        sim.inject_failure(FailureMode.THERMAL_OVERLOAD, onset_step=10, ramp_steps=100)
        detector = RuleDetector()
        anomalies = []
        for _ in range(150):
            snap = sim.step()
            anomalies.extend(detector.detect(snap))
        temp_anomalies = [a for a in anomalies if a.sensor_name == "temperature"]
        assert len(temp_anomalies) > 0, "Should detect temperature anomaly"

    def test_detects_low_coolant_flow(self):
        sim = MachineSimulator(MachineConfig(machine_id="M-CF"), seed=42)
        sim.inject_failure(FailureMode.COOLING_FAILURE, onset_step=10, ramp_steps=100)
        detector = RuleDetector()
        anomalies = []
        for _ in range(150):
            snap = sim.step()
            anomalies.extend(detector.detect(snap))
        flow_anomalies = [a for a in anomalies if a.sensor_name == "coolant_flow"]
        assert len(flow_anomalies) > 0, "Should detect low coolant flow"

    def test_anomaly_has_severity(self, bearing_degradation_machine):
        detector = RuleDetector()
        sim = bearing_degradation_machine
        for _ in range(200):
            snap = sim.step()
            anomalies = detector.detect(snap)
            if anomalies:
                for a in anomalies:
                    assert 0.0 <= a.severity <= 1.0
                    assert a.detector_name == "rule_detector"
                break

    def test_anomaly_has_correct_type(self, bearing_degradation_machine):
        detector = RuleDetector()
        sim = bearing_degradation_machine
        found_trend = False
        for _ in range(200):
            snap = sim.step()
            anomalies = detector.detect(snap)
            for a in anomalies:
                assert a.anomaly_type in (AnomalyType.THRESHOLD_BREACH, AnomalyType.TREND_ANOMALY)
                if a.anomaly_type == AnomalyType.TREND_ANOMALY:
                    found_trend = True
        assert found_trend, "Should detect at least one trend anomaly"

    def test_nan_values_do_not_trigger_anomalies(self):
        from factorymind.simulation.sensors import SensorQualityConfig
        sim = MachineSimulator(
            MachineConfig(machine_id="M-NAN"),
            seed=42,
            quality=SensorQualityConfig(dropout_prob=0.5),
        )
        detector = RuleDetector()
        for _ in range(50):
            snap = sim.step()
            anomalies = detector.detect(snap)
            # NaN readings should not produce anomalies
            for a in anomalies:
                assert a.value == a.value  # not NaN