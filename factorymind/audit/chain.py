"""Tamper-evident audit chain.

The audit chain is a linked list of ``AuditEvent`` objects where each event's
hash includes the previous event's hash. This creates a cryptographic chain:

    Event 1 → hash_1
    Event 2 → hash_2 (includes hash_1)
    Event 3 → hash_3 (includes hash_2)

If any event is modified, its hash changes, which breaks every subsequent
hash. The ``verify_chain()`` function detects this.

Phase 1 uses an in-memory implementation. Phase 4+ will persist to PostgreSQL
or a file-based append-only log.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from factorymind.audit.events import AuditEventFactory, compute_event_hash
from factorymind.domain.enums import AuditEventType
from factorymind.domain.models import AuditEvent


class AuditChain:
    """In-memory tamper-evident audit chain.

    The chain stores events in order and links them via SHA-256 hashes.
    """

    GENESIS_HASH = "0" * 64  # Genesis block has no predecessor.

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._last_hash: str = self.GENESIS_HASH

    @property
    def events(self) -> list[AuditEvent]:
        """Return a read-only copy of all events."""
        return list(self._events)

    @property
    def length(self) -> int:
        return len(self._events)

    @property
    def last_hash(self) -> str:
        return self._last_hash

    def record(
        self,
        machine_id: str,
        actor: str,
        event_type: AuditEventType,
        payload: dict[str, Any],
    ) -> AuditEvent:
        """Record a new event in the chain.

        Args:
            machine_id: Which machine this event relates to.
            actor: Who initiated the event ("agent", "operator", "system").
            event_type: Type of audit event.
            payload: Event-specific data.

        Returns:
            The recorded AuditEvent (with hash).
        """
        event = AuditEventFactory.create(
            machine_id=machine_id,
            actor=actor,
            event_type=event_type,
            payload=payload,
        )

        # Link to chain
        event = AuditEvent(
            event_id=event.event_id,
            timestamp=event.timestamp,
            machine_id=event.machine_id,
            actor=event.actor,
            event_type=event.event_type,
            payload=event.payload,
            previous_hash=self._last_hash,
            event_hash="",
        )

        # Compute hash
        event_hash = compute_event_hash(
            event_id=event.event_id,
            timestamp=event.timestamp.isoformat(),
            machine_id=event.machine_id,
            actor=event.actor,
            event_type=event.event_type.value,
            payload=event.payload,
            previous_hash=event.previous_hash,
        )

        event = AuditEvent(
            event_id=event.event_id,
            timestamp=event.timestamp,
            machine_id=event.machine_id,
            actor=event.actor,
            event_type=event.event_type,
            payload=event.payload,
            previous_hash=event.previous_hash,
            event_hash=event_hash,
        )

        self._events.append(event)
        self._last_hash = event_hash

        return event

    def get_events_for_machine(self, machine_id: str) -> list[AuditEvent]:
        """Return all events for a specific machine."""
        return [e for e in self._events if e.machine_id == machine_id]

    def get_events_by_type(self, event_type: AuditEventType) -> list[AuditEvent]:
        """Return all events of a specific type."""
        return [e for e in self._events if e.event_type == event_type]

    def clear(self) -> None:
        """Clear the chain (for testing)."""
        self._events.clear()
        self._last_hash = self.GENESIS_HASH

    def export(self) -> list[dict]:
        """Export all events as dictionaries (for persistence)."""
        return [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp.isoformat(),
                "machine_id": e.machine_id,
                "actor": e.actor,
                "event_type": e.event_type.value,
                "payload": e.payload,
                "previous_hash": e.previous_hash,
                "event_hash": e.event_hash,
            }
            for e in self._events
        ]