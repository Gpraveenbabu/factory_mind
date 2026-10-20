"""Tests for the root cause analysis engine."""

from __future__ import annotations

import pytest

from factorymind.detection.rules import RuleDetector
from factorymind.domain.enums import FailureMode, HealthState
from factorymind.domain.models import MachineConfig
from factorymind.rca.engine import RCAEngine
from factorymind.simulation.machine import MachineSimulator


class TestRCAEngine:
    def test_healthy_machine_no_root_cause(self, healthy_machine):
        rca = RCAEngine()
        detector = RuleDetector()
        sim = healthy_machine
        for _ in range(50):
            snap = sim.step()
            anomalies = detector.detect(snap)
            result = rca.analyze(snap, anomalies, sim.runtime.degradation_score)
        assert result.root_cause == FailureMode.NONE
        assert result.confidence > 0.5

    def test_identifies_bearing_degradation(self, bearing_degradation_machine):
        rca = RCAEngine()
        detector = RuleDetector()
        sim = bearing_degradation_machine
        results = []
        for _ in range(250):
            snap = sim.step()
            anomalies = detector.detect(snap)
            result = rca.analyze(snap, anomalies, sim.runtime.degradation_score)
            if result.root_cause != FailureMode.NONE:
                results.append(result)

        assert len(results) > 0, "RCA should identify a root cause"
        # The most frequent root cause should be bearing-related
        bearing_results = [
            r for r in results
            if r.root_cause in (FailureMode.BEARING_DEGRADATION, FailureMode.BEARING_FAILURE)
        ]
        assert len(bearing_results) > 0, (
            f"Expected bearing-related root cause, got {[r.root_cause.value for r in results[-5:]]}"
        )

    def test_identifies_thermal_overload(self):
        sim = MachineSimulator(MachineConfig(machine_id="M-TH"), seed=42)
        sim.inject_failure(FailureMode.THERMAL_OVERLOAD, onset_step=20, ramp_steps=150)
        rca = RCAEngine()
        detector = RuleDetector()
        results = []
        for _ in range(250):
            snap = sim.step()
            anomalies = detector.detect(snap)
            result = rca.analyze(snap, anomalies, sim.runtime.degradation_score)
            if result.root_cause != FailureMode.NONE:
                results.append(result.root_cause)
        assert FailureMode.THERMAL_OVERLOAD in results, (
            f"Expected thermal overload in {set(results)}"
        )

    def test_identifies_cooling_failure(self):
        sim = MachineSimulator(MachineConfig(machine_id="M-COOL"), seed=42)
        sim.inject_failure(FailureMode.COOLING_FAILURE, onset_step=20, ramp_steps=150)
        rca = RCAEngine()
        detector = RuleDetector()
        results = []
        for _ in range(250):
            snap = sim.step()
            anomalies = detector.detect(snap)
            result = rca.analyze(snap, anomalies, sim.runtime.degradation_score)
            if result.root_cause != FailureMode.NONE:
                results.append(result.root_cause)
        assert FailureMode.COOLING_FAILURE in results, (
            f"Expected cooling failure in {set(results)}"
        )

    def test_root_cause_has_evidence(self, bearing_degradation_machine):
        rca = RCAEngine()
        detector = RuleDetector()
        sim = bearing_degradation_machine
        for _ in range(250):
            snap = sim.step()
            anomalies = detector.detect(snap)
            result = rca.analyze(snap, anomalies, sim.runtime.degradation_score)
            if result.root_cause != FailureMode.NONE:
                assert len(result.evidence) > 0, "Root cause must have evidence"
                assert 0.0 <= result.confidence <= 1.0
                return
        pytest.fail("No root cause identified")

    def test_confidence_in_valid_range(self, bearing_degradation_machine):
        rca = RCAEngine()
        detector = RuleDetector()
        sim = bearing_degradation_machine
        for _ in range(250):
            snap = sim.step()
            anomalies = detector.detect(snap)
            result = rca.analyze(snap, anomalies, sim.runtime.degradation_score)
            assert 0.0 <= result.confidence <= 1.0