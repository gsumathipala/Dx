"""Audit trail: capture, chaining, immutability and tamper detection."""
from __future__ import annotations

from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from apps.accounts.models import Department
from apps.audit.context import audit_as, suppress_auditing
from apps.audit.hashing import GENESIS_HASH, hash_for_event
from apps.audit.models import AuditEvent, AuditEventError
from apps.audit import protection
from apps.audit.recorder import recorder
from apps.audit.verification import verify_chain


class AuditCaptureTests(TestCase):
    def setUp(self):
        recorder.flush(timeout=5)

    def test_create_update_delete_are_captured_with_diffs(self):
        with audit_as(actor_username="alice", actor_role="manager"):
            dept = Department.objects.create(name="Chemistry", code="CHEM")
            dept.name = "Clinical Chemistry"
            dept.save()
            dept_id = dept.pk
            dept.delete()
        recorder.flush(timeout=5)

        events = AuditEvent.objects.for_entity("accounts.Department", dept_id).order_by("sequence")
        self.assertEqual([e.action for e in events], ["CREATE", "UPDATE", "DELETE"])
        self.assertEqual(events[1].changes["name"], {"old": "Chemistry", "new": "Clinical Chemistry"})
        self.assertTrue(all(e.actor_username == "alice" for e in events))

    def test_save_with_no_change_records_nothing(self):
        with audit_as(actor_username="bob"):
            dept = Department.objects.create(name="Haematology", code="HAEM")
            recorder.flush(timeout=5)
            before = AuditEvent.objects.count()
            dept.save()
        recorder.flush(timeout=5)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_suppressed_context_records_nothing(self):
        before = AuditEvent.objects.count()
        with suppress_auditing():
            Department.objects.create(name="Micro", code="MICRO")
        recorder.flush(timeout=5)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_blocking_event_does_not_overtake_queued_events(self):
        """A synchronous write must not be sequenced before earlier async ones."""
        with audit_as(actor_username="carol"):
            dept = Department.objects.create(name="Serology", code="SERO")  # queued
            dept_id = dept.pk
            dept.delete()  # blocking
        recorder.flush(timeout=5)

        events = AuditEvent.objects.for_entity("accounts.Department", dept_id).order_by("sequence")
        self.assertEqual([e.action for e in events], ["CREATE", "DELETE"])


class ChainIntegrityTests(TestCase):
    def setUp(self):
        protection.install()
        self.addCleanup(protection.remove)
        recorder.flush(timeout=5)
        with audit_as(actor_username="dave"):
            for index in range(5):
                Department.objects.create(name=f"Dept {index}", code=f"D{index}")
        recorder.flush(timeout=5)

    def test_chain_is_continuous_and_verifies(self):
        result = verify_chain()
        self.assertTrue(result.ok, result.summary)
        self.assertEqual(AuditEvent.objects.first().previous_hash,
                         AuditEvent.objects.order_by("-sequence")[1].hash)

    def test_genesis_event_anchors_to_zero_hash(self):
        genesis = AuditEvent.objects.order_by("sequence").first()
        self.assertEqual(genesis.sequence, 1)
        self.assertEqual(genesis.previous_hash, GENESIS_HASH)

    def test_recomputed_hash_matches_stored_hash(self):
        for event in AuditEvent.objects.all()[:10]:
            self.assertEqual(hash_for_event(event), event.hash)

    def test_tampering_is_detected_and_located(self):
        target = AuditEvent.objects.order_by("sequence")[2]
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE audit_events DISABLE TRIGGER dx_audit_no_update")
            cursor.execute(
                "UPDATE audit_events SET actor_username = %s WHERE sequence = %s",
                ["mallory", target.sequence],
            )
            cursor.execute("ALTER TABLE audit_events ENABLE TRIGGER dx_audit_no_update")

        result = verify_chain()
        self.assertFalse(result.ok)
        self.assertIn(f"#{target.sequence}", result.problems[0])

    def test_deleting_an_event_creates_a_detectable_gap(self):
        target = AuditEvent.objects.order_by("sequence")[2]
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE audit_events DISABLE TRIGGER dx_audit_no_delete")
            cursor.execute("DELETE FROM audit_events WHERE sequence = %s", [target.sequence])
            cursor.execute("ALTER TABLE audit_events ENABLE TRIGGER dx_audit_no_delete")

        result = verify_chain()
        self.assertFalse(result.ok)
        self.assertTrue(any("Sequence gap" in problem for problem in result.problems))


class ImmutabilityTests(TestCase):
    def setUp(self):
        protection.install()
        self.addCleanup(protection.remove)
        recorder.flush(timeout=5)
        with audit_as(actor_username="erin"):
            Department.objects.create(name="Immunology", code="IMM")
        recorder.flush(timeout=5)
        self.event = AuditEvent.objects.first()

    def test_orm_update_is_refused(self):
        self.event.actor_username = "mallory"
        with self.assertRaises(AuditEventError):
            self.event.save()

    def test_orm_delete_is_refused(self):
        with self.assertRaises(AuditEventError):
            self.event.delete()

    def test_queryset_update_and_delete_are_refused(self):
        with self.assertRaises(AuditEventError):
            AuditEvent.objects.all().update(actor_username="mallory")
        with self.assertRaises(AuditEventError):
            AuditEvent.objects.all().delete()

    def test_database_triggers_block_raw_sql(self):
        for statement in (
            "UPDATE audit_events SET actor_username = 'mallory'",
            "DELETE FROM audit_events",
            "TRUNCATE audit_events",
        ):
            with self.subTest(statement=statement):
                with self.assertRaises(DatabaseError):
                    with transaction.atomic(), connection.cursor() as cursor:
                        cursor.execute(statement)
