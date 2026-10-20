"""Audit chain verification — tamper detection.

The verifier recomputes the hash of every event in the chain and checks that:
1. Each event's hash matches the stored hash.
2. Each event's ``previous_hash`` matches the previous event's hash.
3. The genesis event's ``previous_hash`` is the genesis constant.

If any check fails, the chain has been tampered with.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from factorymind.audit.chain import AuditChain
from factorymind.audit.events import compute_event_hash
from factorymind.domain.models import AuditEvent


@dataclass(frozen=True)
class VerificationResult:
    """Result of chain verification."""

    valid: bool
    total_events: int = 0
    broken_at_index: int | None = None
    errors: list[str] = field(default_factory=list)


class ChainVerifier:
    """Verifies the integrity of an audit chain."""

    @staticmethod
    def verify(chain: AuditChain) -> VerificationResult:
        """Verify the entire chain.

        Returns a VerificationResult indicating whether the chain is intact.
        """
        events = chain.events
        errors: list[str] = []
        broken_at: int | None = None

        if len(events) == 0:
            return VerificationResult(valid=True, total_events=0)

        previous_hash = AuditChain.GENESIS_HASH

        for i, event in enumerate(events):
            # Check 1: previous_hash links correctly.
            if event.previous_hash != previous_hash:
                msg = (
                    f"Event {i} ({event.event_id}): previous_hash mismatch. "
                    f"Expected {previous_hash[:16]}..., got {event.previous_hash[:16]}..."
                )
                errors.append(msg)
                if broken_at is None:
                    broken_at = i
                break

            # Check 2: event_hash is correct.
            expected_hash = compute_event_hash(
                event_id=event.event_id,
                timestamp=event.timestamp.isoformat(),
                machine_id=event.machine_id,
                actor=event.actor,
                event_type=event.event_type.value,
                payload=event.payload,
                previous_hash=event.previous_hash,
            )

            if event.event_hash != expected_hash:
                msg = (
                    f"Event {i} ({event.event_id}): hash mismatch. "
                    f"Expected {expected_hash[:16]}..., got {event.event_hash[:16]}..."
                )
                errors.append(msg)
                if broken_at is None:
                    broken_at = i
                break

            previous_hash = event.event_hash

        return VerificationResult(
            valid=len(errors) == 0,
            total_events=len(events),
            broken_at_index=broken_at,
            errors=errors,
        )

    @staticmethod
    def verify_event(event: AuditEvent, expected_previous_hash: str) -> bool:
        """Verify a single event's hash."""
        if event.previous_hash != expected_previous_hash:
            return False
        expected_hash = compute_event_hash(
            event_id=event.event_id,
            timestamp=event.timestamp.isoformat(),
            machine_id=event.machine_id,
            actor=event.actor,
            event_type=event.event_type.value,
            payload=event.payload,
            previous_hash=event.previous_hash,
        )
        return event.event_hash == expected_hash