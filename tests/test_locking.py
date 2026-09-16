"""Pessimistic record locking.

The point of these tests is that the *second* user is stopped. A locking
scheme that takes the lock correctly but lets the second save through is worse
than no locking at all, because people trust it.
"""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import locking
from apps.accounts.models import RecordLock
from apps.audit.models import AuditEvent
from apps.common.constants import OrderStatus
from apps.compliance.services import ControlViolation
from apps.laboratory.models import Result
from tests.factories import (
    grant_competency, make_order, make_patient, make_test, make_user, passing_qc,
)

PASSWORD = "Str0ng-Pass!23"
ORDER = "laboratory.Order"


class AcquireTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", password=PASSWORD)
        self.bob = make_user("bob", password=PASSWORD)
        self.patient = make_patient()
        self.order = make_order(self.patient, [])

    def test_the_first_user_takes_the_lock(self):
        state = locking.acquire(ORDER, self.order.pk, self.alice)
        self.assertTrue(state.editable)
        self.assertTrue(state.held_by_me)
        self.assertFalse(state.blocked)

    def test_the_second_user_is_blocked_but_not_errored(self):
        locking.acquire(ORDER, self.order.pk, self.alice)
        state = locking.acquire(ORDER, self.order.pk, self.bob)

        self.assertFalse(state.editable)
        self.assertTrue(state.blocked)
        self.assertEqual(state.holder, "alice")
        self.assertIn("alice", state.message)

    def test_reopening_refreshes_rather_than_duplicating(self):
        first = locking.acquire(ORDER, self.order.pk, self.alice)
        second = locking.acquire(ORDER, self.order.pk, self.alice)

        self.assertEqual(RecordLock.objects.count(), 1)
        self.assertTrue(second.editable)
        self.assertGreaterEqual(second.expires_at, first.expires_at)

    def test_an_expired_lock_is_taken_over(self):
        locking.acquire(ORDER, self.order.pk, self.alice)
        RecordLock.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        state = locking.acquire(ORDER, self.order.pk, self.bob)
        self.assertTrue(state.editable)
        self.assertEqual(RecordLock.objects.get().username, "bob")

    def test_locks_on_different_records_do_not_interfere(self):
        other = make_order(self.patient, [], accession="2026-01-01-9999")
        self.assertTrue(locking.acquire(ORDER, self.order.pk, self.alice).editable)
        self.assertTrue(locking.acquire(ORDER, other.pk, self.bob).editable)

    def test_locks_of_different_types_on_the_same_id_do_not_interfere(self):
        locking.acquire(ORDER, self.order.pk, self.alice)
        state = locking.acquire("patients.Patient", self.order.pk, self.bob)
        self.assertTrue(state.editable)


class ReleaseTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", password=PASSWORD)
        self.bob = make_user("bob", password=PASSWORD)
        self.order = make_order(make_patient(), [])

    def test_releasing_frees_the_record(self):
        locking.acquire(ORDER, self.order.pk, self.alice)
        self.assertTrue(locking.release(ORDER, self.order.pk, self.alice))
        self.assertTrue(locking.acquire(ORDER, self.order.pk, self.bob).editable)

    def test_releasing_a_lock_you_do_not_hold_does_nothing(self):
        """A stale beacon must not free a lock somebody else has since taken."""
        locking.acquire(ORDER, self.order.pk, self.alice)
        self.assertFalse(locking.release(ORDER, self.order.pk, self.bob))
        self.assertEqual(RecordLock.objects.get().username, "alice")

    def test_signing_out_releases_everything(self):
        second = make_order(make_patient(mrn="MRN002"), [], accession="2026-01-01-8888")
        locking.acquire(ORDER, self.order.pk, self.alice)
        locking.acquire(ORDER, second.pk, self.alice)

        self.assertEqual(locking.release_all_for(self.alice), 2)
        self.assertEqual(RecordLock.objects.count(), 0)

    def test_heartbeat_extends_only_your_own_lock(self):
        locking.acquire(ORDER, self.order.pk, self.alice)
        self.assertTrue(locking.heartbeat(ORDER, self.order.pk, self.alice))
        self.assertFalse(locking.heartbeat(ORDER, self.order.pk, self.bob))


class BreakTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", password=PASSWORD)
        self.manager = make_user("mgr", role="manager", password=PASSWORD)
        self.order = make_order(make_patient(), [])
        locking.acquire(ORDER, self.order.pk, self.alice)
        self.lock = RecordLock.objects.get()

    def test_a_manager_can_break_a_lock(self):
        locking.break_lock(self.lock, by_user=self.manager, reason="Alice is off shift.")
        self.assertEqual(RecordLock.objects.count(), 0)

    def test_breaking_is_audited_with_the_reason(self):
        locking.break_lock(self.lock, by_user=self.manager, reason="Alice is off shift.")

        event = AuditEvent.objects.for_entity(ORDER, self.order.pk).first()
        self.assertIn("broken by mgr", event.entity_label)
        self.assertEqual(event.reason, "Alice is off shift.")

    def test_breaking_needs_a_reason(self):
        with self.assertRaises(ControlViolation):
            locking.break_lock(self.lock, by_user=self.manager, reason="   ")
        self.assertEqual(RecordLock.objects.count(), 1)

    def test_a_scientist_cannot_break_a_lock(self):
        scientist = make_user("bms", password=PASSWORD)
        with self.assertRaises(ControlViolation):
            locking.break_lock(self.lock, by_user=scientist, reason="I want it.")
        self.assertEqual(RecordLock.objects.count(), 1)

    def test_the_installer_can_break_a_lock(self):
        """Unsticking the system is the installer's job; reading it is not."""
        installer = make_user("inst", role="installer", password=PASSWORD)
        locking.break_lock(self.lock, by_user=installer, reason="Workstation reimaged.")
        self.assertEqual(RecordLock.objects.count(), 0)


class ResultEntryTests(TestCase):
    """The screen that matters: two scientists on one order."""

    def setUp(self):
        self.alice = make_user("alice", password=PASSWORD)
        self.bob = make_user("bob", password=PASSWORD)
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])
        for user in (self.alice, self.bob):
            grant_competency(user, self.test)
        passing_qc(self.test)
        self.url = reverse("laboratory:result_entry", args=[self.order.pk])

    def test_opening_the_screen_takes_the_lock(self):
        self.client.force_login(self.alice)
        self.client.get(self.url)
        self.assertEqual(RecordLock.objects.get().username, "alice")

    def test_the_second_user_sees_a_read_only_screen(self):
        self.client.force_login(self.alice)
        self.client.get(self.url)

        self.client.force_login(self.bob)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open by alice")
        self.assertContains(response, "Read-only")

    def test_the_second_users_save_is_refused(self):
        self.client.force_login(self.alice)
        self.client.get(self.url)

        self.client.force_login(self.bob)
        response = self.client.post(self.url, {f"result_{self.test.id}": "5.0"})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Result.objects.filter(order=self.order).exists())

    def test_the_holder_can_still_save(self):
        self.client.force_login(self.alice)
        self.client.get(self.url)
        self.client.post(self.url, {f"result_{self.test.id}": "5.0"})

        self.assertTrue(Result.objects.filter(order=self.order, value="5.0").exists())

    def test_saving_releases_the_lock(self):
        self.client.force_login(self.alice)
        self.client.get(self.url)
        self.client.post(self.url, {f"result_{self.test.id}": "5.0"})

        self.assertEqual(RecordLock.objects.count(), 0)

    def test_the_second_user_can_work_once_the_first_leaves(self):
        self.client.force_login(self.alice)
        self.client.get(self.url)
        self.client.post(reverse("accounts:lock_release"), {
            "entity_type": ORDER, "entity_id": str(self.order.pk),
        })

        self.client.force_login(self.bob)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Open by alice")


class PatientRecordTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", role="manager", password=PASSWORD)
        self.bob = make_user("bob", role="manager", password=PASSWORD)
        self.patient = make_patient()

    def test_opening_the_record_reserves_it(self):
        self.client.force_login(self.alice)
        self.client.get(reverse("patients:detail", args=[self.patient.pk]))
        self.assertEqual(RecordLock.objects.get().entity_type, "patients.Patient")

    def test_a_second_user_cannot_edit_a_record_that_is_open(self):
        self.client.force_login(self.alice)
        self.client.get(reverse("patients:detail", args=[self.patient.pk]))

        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("patients:patient_update", args=[self.patient.pk]),
            {"first_name": "Changed", "last_name": "Doe",
             "dob": "1980-05-17", "gender": "F", "mrn": self.patient.mrn},
        )
        self.patient.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.patient.first_name, "Jane")

    def test_the_holder_can_edit(self):
        self.client.force_login(self.alice)
        self.client.get(reverse("patients:detail", args=[self.patient.pk]))
        self.client.post(
            reverse("patients:patient_update", args=[self.patient.pk]),
            {"first_name": "Changed", "last_name": "Doe",
             "dob": "1980-05-17", "gender": "F", "mrn": self.patient.mrn},
        )
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.first_name, "Changed")


class EndpointTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", password=PASSWORD)
        self.order = make_order(make_patient(), [])
        self.client.force_login(self.alice)

    def test_heartbeat_keeps_a_held_lock(self):
        locking.acquire(ORDER, self.order.pk, self.alice)
        response = self.client.post(reverse("accounts:lock_heartbeat"), {
            "entity_type": ORDER, "entity_id": str(self.order.pk),
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["held"])

    def test_heartbeat_reports_a_lost_lock(self):
        bob = make_user("bob", password=PASSWORD)
        locking.acquire(ORDER, self.order.pk, bob)

        response = self.client.post(reverse("accounts:lock_heartbeat"), {
            "entity_type": ORDER, "entity_id": str(self.order.pk),
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["holder"], "bob")

    def test_an_unknown_entity_type_is_refused(self):
        """A closed list, so the table cannot be filled with junk locks."""
        response = self.client.post(reverse("accounts:lock_heartbeat"), {
            "entity_type": "auth.User", "entity_id": "1",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(RecordLock.objects.count(), 0)


class LockScreenTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", password=PASSWORD)
        self.manager = make_user("mgr", role="manager", password=PASSWORD)
        self.patient = make_patient()
        self.order = make_order(self.patient, [], accession="2026-01-01-0042")
        locking.acquire(ORDER, self.order.pk, self.alice)

    def test_a_manager_sees_the_locked_record(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("accounts:lock_list"))
        self.assertContains(response, "alice")
        self.assertContains(response, "2026-01-01-0042")

    def test_the_installer_sees_the_lock_but_not_the_record(self):
        installer = make_user("inst", role="installer", password=PASSWORD)
        self.client.force_login(installer)
        response = self.client.get(reverse("accounts:lock_list"))

        self.assertContains(response, "alice")
        self.assertNotContains(response, "2026-01-01-0042")
        self.assertContains(response, "[redacted]")

    def test_a_scientist_cannot_reach_the_screen(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("accounts:lock_list"))
        self.assertEqual(response.status_code, 403)

    def test_breaking_through_the_screen_needs_a_reason(self):
        lock = RecordLock.objects.get()
        self.client.force_login(self.manager)
        self.client.post(reverse("accounts:lock_break", args=[lock.pk]), {"reason": ""})
        self.assertEqual(RecordLock.objects.count(), 1)

    def test_breaking_through_the_screen_works(self):
        lock = RecordLock.objects.get()
        self.client.force_login(self.manager)
        self.client.post(
            reverse("accounts:lock_break", args=[lock.pk]),
            {"reason": "Alice went home with the record open."},
        )
        self.assertEqual(RecordLock.objects.count(), 0)


class SignOutTests(TestCase):
    def test_signing_out_releases_held_records(self):
        alice = make_user("alice", password=PASSWORD)
        order = make_order(make_patient(), [])
        self.client.force_login(alice)
        locking.acquire(ORDER, order.pk, alice)

        self.client.post(reverse("accounts:logout"))
        self.assertEqual(RecordLock.objects.count(), 0)
