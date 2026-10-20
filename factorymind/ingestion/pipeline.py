"""Telemetry ingestion pipeline.

The pipeline is the entry point for incoming telemetry. It:
1. Validates each snapshot.
2. Buffers readings in a rolling window for feature computation.
3. Emits domain events (telemetry.received, anomaly.detected, etc.).

The pipeline is designed for **in-process** use in Phase 1. In Phase 4+, it
will be backed by Kafka. The domain logic stays the same — only the transport
changes (see ``streaming.py`` in a later phase).

Design: The pipeline is a **passive** component — it stores and validates but
does NOT run detection or RCA. Those are invoked explicitly by the orchestrator.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from factorymind.domain.models import TelemetrySnapshot
from factorymind.ingestion.validation import TelemetryValidator, ValidationResult


# Event handler type — called when a domain event is emitted.
EventHandler = Callable[[str, dict], None]


@dataclass
class IngestionStats:
    """Running statistics for the ingestion pipeline."""

    total_received: int = 0
    total_valid: int = 0
    total_invalid: int = 0
    total_warnings: int = 0


@dataclass
class TelemetryBuffer:
    """A rolling buffer of telemetry snapshots for one machine."""

    machine_id: str
    max_size: int = 500
    _snapshots: deque[TelemetrySnapshot] = field(init=False)

    def __post_init__(self) -> None:
        self._snapshots = deque(maxlen=self.max_size)

    def add(self, snapshot: TelemetrySnapshot) -> None:
        """Add a snapshot to the buffer."""
        self._snapshots.append(snapshot)

    def get_recent(self, n: int) -> list[TelemetrySnapshot]:
        """Return the ``n`` most recent snapshots."""
        if n >= len(self._snapshots):
            return list(self._snapshots)
        return list(self._snapshots)[-n:]

    def latest(self) -> TelemetrySnapshot | None:
        """Return the most recent snapshot, or None if empty."""
        if not self._snapshots:
            return None
        return self._snapshots[-1]

    def __len__(self) -> int:
        return len(self._snapshots)


class IngestionPipeline:
    """In-process telemetry ingestion pipeline.

    Args:
        validator: The telemetry validator to use.
        buffer_size: Maximum snapshots to keep per machine.
        event_handler: Optional callback for domain events.
    """

    def __init__(
        self,
        validator: TelemetryValidator | None = None,
        buffer_size: int = 500,
        event_handler: EventHandler | None = None,
    ) -> None:
        self._validator = validator or TelemetryValidator()
        self._buffers: dict[str, TelemetryBuffer] = {}
        self._buffer_size = buffer_size
        self._event_handler = event_handler
        self.stats = IngestionStats()

    def ingest(self, snapshot: TelemetrySnapshot) -> ValidationResult:
        """Validate and buffer a telemetry snapshot.

        Returns the validation result so callers can react to warnings/errors.
        """
        self.stats.total_received += 1

        # Validate
        result = self._validator.validate(snapshot)
        if result.valid:
            self.stats.total_valid += 1
        else:
            self.stats.total_invalid += 1
        if result.warnings:
            self.stats.total_warnings += 1

        # Buffer (even invalid — downstream may want to inspect)
        if snapshot.machine_id not in self._buffers:
            self._buffers[snapshot.machine_id] = TelemetryBuffer(
                machine_id=snapshot.machine_id,
                max_size=self._buffer_size,
            )
        self._buffers[snapshot.machine_id].add(snapshot)

        # Emit event
        self._emit("telemetry.received", {
            "machine_id": snapshot.machine_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "valid": result.valid,
            "warnings": result.warnings,
            "nan_fraction": result.nan_fraction,
        })

        return result

    def get_buffer(self, machine_id: str) -> TelemetryBuffer | None:
        """Return the telemetry buffer for a machine."""
        return self._buffers.get(machine_id)

    def get_recent(self, machine_id: str, n: int) -> list[TelemetrySnapshot]:
        """Return the ``n`` most recent snapshots for a machine."""
        buf = self._buffers.get(machine_id)
        if buf is None:
            return []
        return buf.get_recent(n)

    def latest(self, machine_id: str) -> TelemetrySnapshot | None:
        """Return the latest snapshot for a machine."""
        buf = self._buffers.get(machine_id)
        if buf is None:
            return None
        return buf.latest()

    @property
    def machine_ids(self) -> list[str]:
        """Return all machine IDs that have been ingested."""
        return list(self._buffers.keys())

    def _emit(self, event_type: str, payload: dict) -> None:
        """Emit a domain event to the handler (if registered)."""
        if self._event_handler is not None:
            self._event_handler(event_type, payload)