"""Audit event definitions and factory.

Audit events are the atomic units of the tamper-evident audit chain. Each
event records who did what, when, and with what payload. Events are linked
via cryptographic hashes.

The ``AuditEventFactory`` creates properly structured events with unique IDs
and timestamps.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from factorymind.domain.enums import AuditEventType
from factorymind.domain.models import AuditEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_event_id() -> str:
    """Generate a unique event ID using UUID4."""
    return str(uuid.uuid4())


class AuditEventFactory:
    """Factory for creating audit events with proper IDs and timestamps."""

    @staticmethod
    def create(
        machine_id: str,
        actor: str,
        event_type: AuditEventType,
        payload: dict,
        timestamp: datetime | None = None,
    ) -> AuditEvent:
        """Create a new audit event (without hash — hashing is done by the chain)."""
        return AuditEvent(
            event_id=_generate_event_id(),
            timestamp=timestamp or _utc_now(),
            machine_id=machine_id,
            actor=actor,
            event_type=event_type,
            payload=payload,
            previous_hash="",  # set by the chain
            event_hash="",       # set by the chain
        )


def compute_event_hash(
    event_id: str,
    timestamp: str,
    machine_id: str,
    actor: str,
    event_type: str,
    payload: dict,
    previous_hash: str,
) -> str:
    """Compute the SHA-256 hash of an audit event.

    The hash includes all fields EXCEPT the hash itself. Including
    ``previous_hash`` creates the chain — modifying any historical event
    breaks all subsequent hashes.
    """
    content = json.dumps({
        "event_id": event_id,
        "timestamp": timestamp,
        "machine_id": machine_id,
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
        "previous_hash": previous_hash,
    }, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()