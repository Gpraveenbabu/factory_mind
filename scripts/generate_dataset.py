"""Generate a synthetic industrial dataset for FactoryMind.

Usage:
    python scripts/generate_dataset.py \
        --machines 100 \
        --duration 1000 \
        --seed 42 \
        --output data/synthetic/

This script creates multiple machines, some healthy and some with injected
failures, and writes the telemetry to CSV files.

Output structure:
    data/synthetic/
    ├── telemetry.csv         # All readings (long format)
    ├── machine_labels.csv    # Machine metadata + injected failure mode
    └── anomaly_labels.csv   # Ground-truth anomaly labels (for evaluation)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import numpy as np

# Ensure the factorymind package is importable when running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factorymind.domain.enums import FailureMode
from factorymind.domain.models import MachineConfig
from factorymind.simulation.machine import MachineSimulator
from factorymind.simulation.sensors import SensorQualityConfig


def generate_dataset(
    num_machines: int = 100,
    duration: int = 1000,
    seed: int = 42,
    output_dir: str = "data/synthetic",
    failure_fraction: float = 0.3,
) -> None:
    """Generate the synthetic dataset.

    Args:
        num_machines: Number of machines to simulate.
        duration: Number of time steps per machine.
        seed: Random seed for reproducibility.
        output_dir: Output directory for CSV files.
        failure_fraction: Fraction of machines that will have a failure injected.
    """
    rng = np.random.default_rng(seed)
    os.makedirs(output_dir, exist_ok=True)

    all_failure_modes = [
        FailureMode.BEARING_DEGRADATION,
        FailureMode.BEARING_FAILURE,
        FailureMode.THERMAL_OVERLOAD,
        FailureMode.MECHANICAL_IMBALANCE,
        FailureMode.MOTOR_OVERLOAD,
        FailureMode.COOLING_FAILURE,
    ]

    # Determine which machines get failures.
    num_failures = int(num_machines * failure_fraction)
    machine_indices = list(range(num_machines))
    failure_machine_indices = rng.choice(machine_indices, size=num_failures, replace=False)
    failure_machine_set = set(failure_machine_indices.tolist())

    # Open output files.
    telemetry_path = os.path.join(output_dir, "telemetry.csv")
    labels_path = os.path.join(output_dir, "machine_labels.csv")
    anomaly_path = os.path.join(output_dir, "anomaly_labels.csv")

    sensor_names = [
        "temperature", "vibration", "pressure", "motor_current",
        "rpm", "load", "coolant_temperature", "coolant_flow", "acoustic_level",
    ]

    with open(telemetry_path, "w", newline="") as f_telem, \
         open(labels_path, "w", newline="") as f_labels, \
         open(anomaly_path, "w", newline="") as f_anom:

        writer_telem = csv.writer(f_telem)
        writer_labels = csv.writer(f_labels)
        writer_anom = csv.writer(f_anom)

        # Headers
        writer_telem.writerow(["machine_id", "step", "timestamp"] + sensor_names)
        writer_labels.writerow(["machine_id", "failure_mode", "onset_step", "ramp_steps"])
        writer_anom.writerow(["machine_id", "step", "is_anomalous", "degradation_score", "health_state"])

        for i in range(num_machines):
            machine_id = f"M-{i:04d}"
            machine_seed = seed + i

            sim = MachineSimulator(
                config=MachineConfig(machine_id=machine_id),
                seed=machine_seed,
            )

            failure_mode = FailureMode.NONE
            onset_step = 0
            ramp_steps = 1

            if i in failure_machine_set:
                failure_mode = rng.choice(all_failure_modes)
                onset_step = int(rng.integers(duration // 4, duration // 2))
                ramp_steps = int(rng.integers(100, 300))
                sim.inject_failure(
                    mode=failure_mode,
                    onset_step=onset_step,
                    ramp_steps=ramp_steps,
                )

            writer_labels.writerow([
                machine_id,
                failure_mode.value,
                onset_step if failure_mode != FailureMode.NONE else "",
                ramp_steps if failure_mode != FailureMode.NONE else "",
            ])

            snapshots = sim.run(duration)

            for step, snapshot in enumerate(snapshots):
                row = [machine_id, step, snapshot.timestamp.isoformat()]
                row.extend([snapshot.readings.get(s, float("nan")) for s in sensor_names])
                writer_telem.writerow(row)

                # Anomaly label: anomalous if degradation score > 0.2
                is_anomalous = sim.runtime.degradation_score > 0.2
                writer_anom.writerow([
                    machine_id,
                    step,
                    int(is_anomalous),
                    sim.runtime.degradation_score,
                    sim.runtime.health.value,
                ])

            if (i + 1) % 10 == 0:
                print(f"Generated {i + 1}/{num_machines} machines...")

    print(f"\nDataset generated in {output_dir}")
    print(f"  Telemetry: {telemetry_path}")
    print(f"  Labels:    {labels_path}")
    print(f"  Anomalies: {anomaly_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate FactoryMind synthetic dataset.")
    parser.add_argument("--machines", type=int, default=100, help="Number of machines to simulate.")
    parser.add_argument("--duration", type=int, default=1000, help="Number of time steps per machine.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--output", type=str, default="data/synthetic", help="Output directory.")
    parser.add_argument("--failure-fraction", type=float, default=0.3, help="Fraction of machines with failures.")
    args = parser.parse_args()

    generate_dataset(
        num_machines=args.machines,
        duration=args.duration,
        seed=args.seed,
        output_dir=args.output,
        failure_fraction=args.failure_fraction,
    )


if __name__ == "__main__":
    main()