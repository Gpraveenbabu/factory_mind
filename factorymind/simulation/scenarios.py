"""Predefined failure scenarios for testing and evaluation.

Each scenario encapsulates a complete simulation setup: machine config, failure
injection, data-quality settings, and the expected outcome. These are used by:
- The evaluation framework (Phase 2) for benchmarking.
- The integration tests for verifying end-to-end behavior.
- The demo script for the polished demonstration.

Scenarios are **reproducible** — same seed always produces the same trajectory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factorymind.domain.enums import FailureMode, HealthState, MachineState
from factorymind.domain.models import MachineConfig
from factorymind.simulation.machine import MachineSimulator
from factorymind.simulation.sensors import SensorQualityConfig


@dataclass(frozen=True)
class ScenarioResult:
    """Expected outcome for a scenario — used for assertions in tests."""

    expected_failure: FailureMode
    expected_final_health: HealthState
    expected_final_state: MachineState
    expected_anomaly_sensors: list[str]  # sensors that should show anomalies
    description: str


@dataclass(frozen=True)
class Scenario:
    """A complete simulation scenario."""

    name: str
    description: str
    machine_id: str
    seed: int
    num_steps: int
    failure_mode: FailureMode
    failure_onset_step: int
    failure_ramp_steps: int
    quality: SensorQualityConfig = field(default_factory=SensorQualityConfig)
    expected: ScenarioResult = field(default_factory=lambda: ScenarioResult(
        expected_failure=FailureMode.NONE,
        expected_final_health=HealthState.HEALTHY,
        expected_final_state=MachineState.RUNNING,
        expected_anomaly_sensors=[],
        description="",
    ))

    def create_simulator(self) -> MachineSimulator:
        """Create a configured ``MachineSimulator`` for this scenario."""
        sim = MachineSimulator(
            config=MachineConfig(machine_id=self.machine_id),
            seed=self.seed,
            quality=self.quality,
        )
        if self.failure_mode != FailureMode.NONE:
            sim.inject_failure(
                mode=self.failure_mode,
                onset_step=self.failure_onset_step,
                ramp_steps=self.failure_ramp_steps,
            )
        return sim


# --- Predefined Scenarios ---

SCENARIOS: list[Scenario] = [
    Scenario(
        name="healthy_machine",
        description="A healthy machine running normally for the full duration.",
        machine_id="M-HEALTHY-01",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.NONE,
        failure_onset_step=0,
        failure_ramp_steps=1,
        expected=ScenarioResult(
            expected_failure=FailureMode.NONE,
            expected_final_health=HealthState.HEALTHY,
            expected_final_state=MachineState.RUNNING,
            expected_anomaly_sensors=[],
            description="No anomalies expected; machine stays healthy.",
        ),
    ),
    Scenario(
        name="gradual_bearing_degradation",
        description="Bearing degradation starting at step 100, ramping over 300 steps.",
        machine_id="M-BRG-001",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.BEARING_DEGRADATION,
        failure_onset_step=100,
        failure_ramp_steps=300,
        expected=ScenarioResult(
            expected_failure=FailureMode.BEARING_DEGRADATION,
            expected_final_health=HealthState.CRITICAL_FAILURE,
            expected_final_state=MachineState.CRITICAL,
            expected_anomaly_sensors=["vibration", "temperature", "motor_current", "acoustic_level"],
            description="Vibration rises first, followed by temperature and current.",
        ),
    ),
    Scenario(
        name="sudden_bearing_failure",
        description="Sudden bearing failure: rapid onset at step 200.",
        machine_id="M-BRG-002",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.BEARING_FAILURE,
        failure_onset_step=200,
        failure_ramp_steps=50,
        expected=ScenarioResult(
            expected_failure=FailureMode.BEARING_FAILURE,
            expected_final_health=HealthState.CRITICAL_FAILURE,
            expected_final_state=MachineState.CRITICAL,
            expected_anomaly_sensors=["vibration", "temperature", "motor_current", "acoustic_level", "rpm"],
            description="Sudden vibration spike and temperature jump.",
        ),
    ),
    Scenario(
        name="thermal_overload",
        description="Thermal overload: sigmoidal temperature rise starting at step 150.",
        machine_id="M-THRM-001",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.THERMAL_OVERLOAD,
        failure_onset_step=150,
        failure_ramp_steps=250,
        expected=ScenarioResult(
            expected_failure=FailureMode.THERMAL_OVERLOAD,
            expected_final_health=HealthState.SEVERE_DEGRADATION,
            expected_final_state=MachineState.CRITICAL,
            expected_anomaly_sensors=["temperature", "coolant_temperature", "coolant_flow"],
            description="Temperature rises sigmoidally, cooling system overwhelmed.",
        ),
    ),
    Scenario(
        name="cooling_failure",
        description="Cooling system failure: coolant flow drops, temperature cascades.",
        machine_id="M-COOL-001",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.COOLING_FAILURE,
        failure_onset_step=100,
        failure_ramp_steps=300,
        expected=ScenarioResult(
            expected_failure=FailureMode.COOLING_FAILURE,
            expected_final_health=HealthState.SEVERE_DEGRADATION,
            expected_final_state=MachineState.CRITICAL,
            expected_anomaly_sensors=["coolant_flow", "coolant_temperature", "temperature"],
            description="Coolant flow drops, temperature cascades upward.",
        ),
    ),
    Scenario(
        name="mechanical_imbalance",
        description="Mechanical imbalance: vibration increases, pressure fluctuates.",
        machine_id="M-IMB-001",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.MECHANICAL_IMBALANCE,
        failure_onset_step=100,
        failure_ramp_steps=300,
        expected=ScenarioResult(
            expected_failure=FailureMode.MECHANICAL_IMBALANCE,
            expected_final_health=HealthState.DEVELOPING_FAULT,
            expected_final_state=MachineState.WARNING,
            expected_anomaly_sensors=["vibration", "pressure", "motor_current"],
            description="Vibration increases, pressure fluctuates.",
        ),
    ),
    Scenario(
        name="motor_overload",
        description="Motor overload: current spikes first, temperature follows.",
        machine_id="M-MOT-001",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.MOTOR_OVERLOAD,
        failure_onset_step=100,
        failure_ramp_steps=300,
        expected=ScenarioResult(
            expected_failure=FailureMode.MOTOR_OVERLOAD,
            expected_final_health=HealthState.SEVERE_DEGRADATION,
            expected_final_state=MachineState.CRITICAL,
            expected_anomaly_sensors=["motor_current", "temperature", "load", "rpm"],
            description="Current spikes, temperature follows, rpm drops.",
        ),
    ),
    Scenario(
        name="sensor_dropout",
        description="Sensor dropout: readings missing due to communication issues.",
        machine_id="M-SENS-001",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.NONE,
        failure_onset_step=0,
        failure_ramp_steps=1,
        quality=SensorQualityConfig(dropout_prob=0.1),
        expected=ScenarioResult(
            expected_failure=FailureMode.NONE,
            expected_final_health=HealthState.HEALTHY,
            expected_final_state=MachineState.RUNNING,
            expected_anomaly_sensors=[],
            description="Some readings are NaN; no real machine fault.",
        ),
    ),
    Scenario(
        name="sensor_drift",
        description="Sensor drift: readings slowly drift from true value.",
        machine_id="M-SENS-002",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.NONE,
        failure_onset_step=0,
        failure_ramp_steps=1,
        quality=SensorQualityConfig(drift_rate=0.02),
        expected=ScenarioResult(
            expected_failure=FailureMode.NONE,
            expected_final_health=HealthState.HEALTHY,
            expected_final_state=MachineState.RUNNING,
            expected_anomaly_sensors=[],
            description="Slow drift; may trigger false anomaly if not handled.",
        ),
    ),
    Scenario(
        name="sensor_stuck",
        description="Sensor stuck: one sensor stops updating and repeats last value.",
        machine_id="M-SENS-003",
        seed=42,
        num_steps=500,
        failure_mode=FailureMode.NONE,
        failure_onset_step=0,
        failure_ramp_steps=1,
        quality=SensorQualityConfig(stuck_prob=0.01),
        expected=ScenarioResult(
            expected_failure=FailureMode.NONE,
            expected_final_health=HealthState.HEALTHY,
            expected_final_state=MachineState.RUNNING,
            expected_anomaly_sensors=[],
            description="Stuck sensor should be detected as sensor fault, not machine failure.",
        ),
    ),
]


def get_scenario(name: str) -> Scenario:
    """Look up a scenario by name."""
    for s in SCENARIOS:
        if s.name == name:
            return s
    raise KeyError(f"Scenario '{name}' not found. Available: {[s.name for s in SCENARIOS]}")


def get_demo_scenario() -> Scenario:
    """Return the scenario used for the polished end-to-end demo."""
    return get_scenario("gradual_bearing_degradation")