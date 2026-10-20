"""Machine simulator — combines sensor generation with failure trajectory injection.

The ``MachineSimulator`` is the single entry point for generating synthetic
industrial telemetry. It:
1. Holds a ``SensorGenerator`` for correlated baseline readings.
2. Optionally holds a ``FailureProfile`` that injects temporal deviations.
3. Steps through time, producing ``TelemetrySnapshot`` objects.
4. Tracks runtime state (degradation score, health state, failure progress).

Key design decisions:
- The simulator is **deterministic** given the same seed.
- Failure injection is **progressive** — not instantaneous.
- A machine can start healthy and develop a fault mid-simulation.
- Sensor faults are injected at the sensor layer, not as machine deviations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from factorymind.domain.enums import FailureMode, HealthState, MachineState
from factorymind.domain.models import MachineConfig, MachineRuntimeState, TelemetrySnapshot
from factorymind.simulation.failures import FailureProfile, get_failure_profile
from factorymind.simulation.sensors import SensorGenerator, SensorQualityConfig, get_sensor_specs


def _health_from_degradation(score: float) -> HealthState:
    """Map a degradation score to a HealthState."""
    if score < 0.2:
        return HealthState.HEALTHY
    if score < 0.5:
        return HealthState.EARLY_DEGRADATION
    if score < 0.75:
        return HealthState.DEVELOPING_FAULT
    if score < 0.95:
        return HealthState.SEVERE_DEGRADATION
    return HealthState.CRITICAL_FAILURE


def _machine_state_from_health(health: HealthState) -> MachineState:
    """Map health to a control-system machine state."""
    mapping = {
        HealthState.HEALTHY: MachineState.RUNNING,
        HealthState.EARLY_DEGRADATION: MachineState.DEGRADING,
        HealthState.DEVELOPING_FAULT: MachineState.WARNING,
        HealthState.SEVERE_DEGRADATION: MachineState.CRITICAL,
        HealthState.CRITICAL_FAILURE: MachineState.CRITICAL,
    }
    return mapping.get(health, MachineState.RUNNING)


@dataclass
class MachineSimulator:
    """Simulates one industrial machine over time.

    Args:
        config: Machine configuration (ID, model, nominal values).
        seed: Random seed for reproducibility.
        noise_std: Base noise standard deviation.
        quality: Sensor data-quality configuration.
        sampling_interval_s: Seconds between readings.
    """

    config: MachineConfig
    seed: int = 42
    noise_std: float = 0.5
    quality: SensorQualityConfig = field(default_factory=SensorQualityConfig)
    sampling_interval_s: int = 60

    # Internal state (not in __init__ args due to default_factory needs).
    _generator: SensorGenerator = field(init=False)
    _runtime: MachineRuntimeState = field(init=False)
    _failure_profile: FailureProfile | None = field(init=False, default=None)
    _failure_onset_step: int = field(init=False, default=0)
    _failure_ramp_steps: int = field(init=False, default=200)
    _start_time: datetime = field(init=False)

    def __post_init__(self) -> None:
        self._generator = SensorGenerator(
            specs=get_sensor_specs(),
            seed=self.seed,
            noise_std=self.noise_std,
            quality=self.quality,
        )
        self._runtime = MachineRuntimeState(machine_id=self.config.machine_id)
        self._start_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    @property
    def runtime(self) -> MachineRuntimeState:
        """Current runtime state (read-only view)."""
        return self._runtime

    @property
    def machine_id(self) -> str:
        return self.config.machine_id

    def inject_failure(
        self,
        mode: FailureMode,
        onset_step: int = 0,
        ramp_steps: int = 200,
    ) -> None:
        """Schedule a failure to begin at ``onset_step`` and ramp over ``ramp_steps``.

        Args:
            mode: The failure mode to inject.
            onset_step: Step index at which the failure begins.
            ramp_steps: Number of steps for the failure to reach full severity.
        """
        self._failure_profile = get_failure_profile(mode)
        self._failure_onset_step = onset_step
        self._failure_ramp_steps = max(ramp_steps, 1)
        self._runtime.active_failure = mode

    def step(self) -> TelemetrySnapshot:
        """Advance the simulation by one step and return the telemetry snapshot."""
        step = self._runtime.current_step
        timestamp = self._start_time + timedelta(seconds=step * self.sampling_interval_s)

        # Compute failure progress [0, 1] if a failure is active.
        deviations: dict[str, float] = {}
        if self._failure_profile is not None and step >= self._failure_onset_step:
            progress = min(
                (step - self._failure_onset_step) / self._failure_ramp_steps,
                1.0,
            )
            deviations = self._failure_profile.deviation_fn(progress)
            self._runtime.failure_progress = progress
            self._runtime.degradation_score = self._failure_profile.degradation_fn(progress)
            self._runtime.health = _health_from_degradation(self._runtime.degradation_score)
            self._runtime.state = _machine_state_from_health(self._runtime.health)

        # Generate correlated sensor readings with deviations applied.
        readings = self._generator.step(deviations=deviations)

        # Build quality map: NaN = missing (quality 0), else 1.
        quality = {
            name: (0.0 if (v != v) else 1.0)  # v != v checks for NaN
            for name, v in readings.items()
        }

        snapshot = TelemetrySnapshot(
            machine_id=self.config.machine_id,
            timestamp=timestamp,
            readings=readings,
            quality=quality,
        )

        self._runtime.current_step += 1
        self._runtime.last_updated = timestamp

        return snapshot

    def run(self, num_steps: int) -> list[TelemetrySnapshot]:
        """Run the simulation for ``num_steps`` and return all snapshots."""
        return [self.step() for _ in range(num_steps)]

    def reset(self, seed: int | None = None) -> None:
        """Reset the simulator to its initial state."""
        if seed is not None:
            self.seed = seed
        self._generator = SensorGenerator(
            specs=get_sensor_specs(),
            seed=self.seed,
            noise_std=self.noise_std,
            quality=self.quality,
        )
        self._runtime = MachineRuntimeState(machine_id=self.config.machine_id)
        self._failure_profile = None
        self._failure_onset_step = 0
        self._runtime.current_step = 0

    def inject_sensor_fault(self, sensor_name: str) -> None:
        """Inject a stuck-value fault on a specific sensor.

        This simulates a sensor fault without real machine degradation.
        The RCA engine must detect this as a sensor_fault, not a real failure.
        """
        if sensor_name in self._generator._states:
            self._generator._states[sensor_name].stuck = True
            # Also set a large drift to make it obviously wrong
            self._generator._states[sensor_name].drift_bias = 50.0