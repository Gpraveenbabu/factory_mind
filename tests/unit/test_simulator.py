"""Tests for the industrial machine simulator."""

from __future__ import annotations

import math

import pytest

from factorymind.domain.enums import FailureMode, HealthState, MachineState
from factorymind.domain.models import MachineConfig, TelemetrySnapshot
from factorymind.simulation.machine import MachineSimulator
from factorymind.simulation.sensors import SensorQualityConfig, get_sensor_specs
from factorymind.simulation.scenarios import get_scenario, SCENARIOS


class TestSensorGenerator:
    def test_generates_all_sensors(self, healthy_machine):
        snapshot = healthy_machine.step()
        expected = set(get_sensor_specs().keys())
        assert set(snapshot.readings.keys()) == expected

    def test_healthy_values_within_nominal_range(self, healthy_machine):
        """Healthy machine readings should be within 3-sigma of nominal."""
        snapshots = healthy_machine.run(100)
        specs = get_sensor_specs()
        for name, spec in specs.items():
            values = [s.readings[name] for s in snapshots if s.readings[name] == s.readings[name]]
            mean = sum(values) / len(values)
            # Mean should be close to nominal (within 2-sigma)
            assert abs(mean - spec.nominal_mean) < 2 * spec.nominal_std, (
                f"{name} mean {mean:.2f} too far from nominal {spec.nominal_mean}"
            )

    def test_deterministic_with_seed(self):
        """Same seed should produce same readings."""
        sim1 = MachineSimulator(MachineConfig(machine_id="M-1"), seed=42)
        sim2 = MachineSimulator(MachineConfig(machine_id="M-1"), seed=42)
        snap1 = sim1.step()
        snap2 = sim2.step()
        assert snap1.readings == snap2.readings

    def test_different_seeds_produce_different_readings(self):
        sim1 = MachineSimulator(MachineConfig(machine_id="M-1"), seed=42)
        sim2 = MachineSimulator(MachineConfig(machine_id="M-1"), seed=99)
        snap1 = sim1.step()
        snap2 = sim2.step()
        assert snap1.readings != snap2.readings

    def test_dropout_produces_nan(self):
        sim = MachineSimulator(
            MachineConfig(machine_id="M-DROP"),
            seed=42,
            quality=SensorQualityConfig(dropout_prob=1.0),  # force all NaN
        )
        snapshot = sim.step()
        for value in snapshot.readings.values():
            assert value != value  # NaN check

    def test_quality_map_reflects_nan(self):
        sim = MachineSimulator(
            MachineConfig(machine_id="M-Q"),
            seed=42,
            quality=SensorQualityConfig(dropout_prob=1.0),
        )
        snapshot = sim.step()
        for name, quality in snapshot.quality.items():
            assert quality == 0.0


class TestFailureInjection:
    def test_bearing_degradation_increases_vibration(self, bearing_degradation_machine):
        """Vibration should increase over time with bearing degradation."""
        sim = bearing_degradation_machine
        early = [sim.step() for _ in range(55)]  # before onset + a few after
        late = [sim.step() for _ in range(150)]

        early_vibration = [s.readings["vibration"] for s in early[-5:]]
        late_vibration = [s.readings["vibration"] for s in late[-5:]]

        early_mean = sum(early_vibration) / len(early_vibration)
        late_mean = sum(late_vibration) / len(late_vibration)

        assert late_mean > early_mean, (
            f"Vibration should increase: early={early_mean:.2f}, late={late_mean:.2f}"
        )

    def test_thermal_overload_increases_temperature(self):
        sim = MachineSimulator(MachineConfig(machine_id="M-THRM"), seed=42)
        sim.inject_failure(FailureMode.THERMAL_OVERLOAD, onset_step=10, ramp_steps=100)
        healthy = sim.step()  # step 0
        for _ in range(120):
            sim.step()
        degraded = sim.step()
        assert degraded.readings["temperature"] > healthy.readings["temperature"]

    def test_cooling_failure_decreases_coolant_flow(self):
        sim = MachineSimulator(MachineConfig(machine_id="M-COOL"), seed=42)
        sim.inject_failure(FailureMode.COOLING_FAILURE, onset_step=10, ramp_steps=100)
        healthy = sim.step()
        for _ in range(120):
            sim.step()
        degraded = sim.step()
        assert degraded.readings["coolant_flow"] < healthy.readings["coolant_flow"]

    def test_degradation_score_progresses(self, bearing_degradation_machine):
        sim = bearing_degradation_machine
        sim.run(45)  # before onset (onset at step 50)
        assert sim.runtime.degradation_score == 0.0
        sim.run(165)  # ramp through to step 210
        assert sim.runtime.degradation_score > 0.5

    def test_health_state_transitions(self, bearing_degradation_machine):
        sim = bearing_degradation_machine
        sim.run(50)
        assert sim.runtime.health == HealthState.HEALTHY
        sim.run(50)  # early degradation
        assert sim.runtime.health in (HealthState.HEALTHY, HealthState.EARLY_DEGRADATION)
        sim.run(100)  # severe
        assert sim.runtime.health in (HealthState.SEVERE_DEGRADATION, HealthState.CRITICAL_FAILURE)


class TestScenarios:
    def test_all_scenarios_create_simulators(self):
        for scenario in SCENARIOS:
            sim = scenario.create_simulator()
            assert sim is not None
            assert sim.machine_id == scenario.machine_id

    def test_healthy_scenario_stays_healthy(self):
        scenario = get_scenario("healthy_machine")
        sim = scenario.create_simulator()
        sim.run(scenario.num_steps)
        assert sim.runtime.health == scenario.expected.expected_final_health

    def test_bearing_degradation_scenario_reaches_critical(self):
        scenario = get_scenario("gradual_bearing_degradation")
        sim = scenario.create_simulator()
        sim.run(scenario.num_steps)
        assert sim.runtime.degradation_score > 0.9