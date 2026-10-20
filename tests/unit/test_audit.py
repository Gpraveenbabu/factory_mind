"""Tests for the tamper-evident audit chain."""

from __future__ import annotations

import pytest

from factorymind.audit.chain import AuditChain
from factorymind.audit.verification import ChainVerifier
from factorymind.domain.enums import AuditEventType


class TestAuditChain:
    def test_empty_chain_verifies(self, audit_chain):
        result = ChainVerifier.verify(audit_chain)
        assert result.valid is True
        assert result.total_events == 0

    def test_record_event(self, audit_chain):
        event = audit_chain.record(
            machine_id="M-1",
            actor="system",
            event_type=AuditEventType.TELEMETRY_RECEIVED,
            payload={"sensor": "temperature", "value": 75.0},
        )
        assert event.event_id != ""
        assert event.event_hash != ""
        assert event.previous_hash == AuditChain.GENESIS_HASH
        assert audit_chain.length == 1

    def test_chain_links(self, audit_chain):
        e1 = audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {"v": 1})
        e2 = audit_chain.record("M-1", "system", AuditEventType.ANOMALY_DETECTED, {"v": 2})
        e3 = audit_chain.record("M-1", "agent", AuditEventType.AGENT_RECOMMENDATION, {"v": 3})

        assert e2.previous_hash == e1.event_hash
        assert e3.previous_hash == e2.event_hash
        assert audit_chain.last_hash == e3.event_hash

    def test_verify_valid_chain(self, audit_chain):
        for i in range(10):
            audit_chain.record(
                machine_id="M-1",
                actor="system",
                event_type=AuditEventType.TELEMETRY_RECEIVED,
                payload={"step": i},
            )
        result = ChainVerifier.verify(audit_chain)
        assert result.valid is True
        assert result.total_events == 10

    def test_tamper_detection_modify_payload(self, audit_chain):
        """Modifying an event's payload must break the chain."""
        audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {"v": 1})
        audit_chain.record("M-1", "system", AuditEventType.ANOMALY_DETECTED, {"v": 2})
        audit_chain.record("M-1", "agent", AuditEventType.AGENT_RECOMMENDATION, {"v": 3})

        # Tamper: modify the first event's payload
        original = audit_chain._events[0]
        audit_chain._events[0] = type(original)(
            event_id=original.event_id,
            timestamp=original.timestamp,
            machine_id=original.machine_id,
            actor=original.actor,
            event_type=original.event_type,
            payload={"v": 999},  # TAMPERED!
            previous_hash=original.previous_hash,
            event_hash=original.event_hash,
        )

        result = ChainVerifier.verify(audit_chain)
        assert result.valid is False
        assert result.broken_at_index is not None

    def test_tamper_detection_modify_hash(self, audit_chain):
        """Modifying an event's hash must break the chain."""
        audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {"v": 1})
        audit_chain.record("M-1", "system", AuditEventType.ANOMALY_DETECTED, {"v": 2})

        # Tamper: modify the first event's hash
        original = audit_chain._events[0]
        audit_chain._events[0] = type(original)(
            event_id=original.event_id,
            timestamp=original.timestamp,
            machine_id=original.machine_id,
            actor=original.actor,
            event_type=original.event_type,
            payload=original.payload,
            previous_hash=original.previous_hash,
            event_hash="deadbeef" * 8,  # TAMPERED HASH
        )

        result = ChainVerifier.verify(audit_chain)
        assert result.valid is False

    def test_tamper_detection_insert_fake_event(self, audit_chain):
        """Inserting a fake event must break the chain."""
        audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {"v": 1})
        audit_chain.record("M-1", "system", AuditEventType.ANOMALY_DETECTED, {"v": 2})

        # Insert a fake event at position 1
        fake_event = audit_chain._events[0].__class__(
            event_id="fake-id",
            timestamp=audit_chain._events[0].timestamp,
            machine_id="M-1",
            actor="attacker",
            event_type=AuditEventType.ACTION_EXECUTED,
            payload={"malicious": True},
            previous_hash="wrong",
            event_hash="wrong",
        )
        audit_chain._events.insert(1, fake_event)

        result = ChainVerifier.verify(audit_chain)
        assert result.valid is False

    def test_get_events_for_machine(self, audit_chain):
        audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {})
        audit_chain.record("M-2", "system", AuditEventType.TELEMETRY_RECEIVED, {})
        audit_chain.record("M-1", "system", AuditEventType.ANOMALY_DETECTED, {})

        m1_events = audit_chain.get_events_for_machine("M-1")
        assert len(m1_events) == 2
        m2_events = audit_chain.get_events_for_machine("M-2")
        assert len(m2_events) == 1

    def test_get_events_by_type(self, audit_chain):
        audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {})
        audit_chain.record("M-1", "system", AuditEventType.ANOMALY_DETECTED, {})
        audit_chain.record("M-1", "system", AuditEventType.ANOMALY_DETECTED, {})

        anomalies = audit_chain.get_events_by_type(AuditEventType.ANOMALY_DETECTED)
        assert len(anomalies) == 2

    def test_export(self, audit_chain):
        audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {"v": 1})
        exported = audit_chain.export()
        assert len(exported) == 1
        assert exported[0]["machine_id"] == "M-1"
        assert exported[0]["event_hash"] != ""

    def test_clear(self, audit_chain):
        audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {})
        audit_chain.clear()
        assert audit_chain.length == 0
        assert audit_chain.last_hash == AuditChain.GENESIS_HASH

    def test_unique_event_ids(self, audit_chain):
        ids = set()
        for i in range(100):
            event = audit_chain.record("M-1", "system", AuditEventType.TELEMETRY_RECEIVED, {"i": i})
            assert event.event_id not in ids
            ids.add(event.event_id)
        assert len(ids) == 100