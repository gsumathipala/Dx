"""The installer role, the PHI barrier, and account administration."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.audit.recorder import recorder
from apps.common.constants import Role
from tests.factories import make_department, make_patient, make_test, make_user

User = get_user_model()
PASSWORD = "Str0ng-Pass!23"


def make_installer(username="installer", password=PASSWORD):
    return User.objects.create_user(
        username=username, password=password, name="System Installer",
        role=Role.INSTALLER,
    )


class InstallerRoleTests(TestCase):
    def setUp(self):
        self.installer = make_installer()

    def test_installer_is_not_lab_staff(self):
        self.assertFalse(self.installer.is_lab_staff)
        self.assertFalse(self.installer.is_admin)
        self.assertTrue(self.installer.is_installer)
        self.assertTrue(self.installer.is_system_staff)

    def test_installer_may_not_see_patient_data(self):
        self.assertFalse(self.installer.may_see_patient_data)

    def test_every_other_role_may_see_patient_data(self):
        for role in (Role.ADMIN, Role.MANAGER, Role.SCIENTIST, Role.MEDIC,
                     Role.CLERK, Role.PHLEBOTOMIST):
            user = make_user(f"u-{role}", role=role)
            self.assertTrue(user.may_see_patient_data, f"{role} should see patient data")


class PHIBarrierTests(TestCase):
    """The barrier must block, not merely hide the links."""

    def setUp(self):
        self.installer = make_installer()
        self.client.force_login(self.installer)
        make_patient(mrn="MRN-BARRIER")

    def test_clinical_screens_are_refused(self):
        for name in ("patients:patient_list", "laboratory:results",
                     "laboratory:accessioning", "clinical:critical_values",
                     "reporting:reports", "specialty:histology",
                     "billing:invoice_list"):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_screens_that_leak_patient_identifiers_are_refused(self):
        for name in ("operations:search", "compliance:phi_access_list",
                     "compliance:disclosure_list", "operations:tracking"):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_a_patient_record_cannot_be_reached_by_typing_its_url(self):
        patient = make_patient(mrn="MRN-DIRECT")
        response = self.client.get(reverse("patients:detail", args=[patient.pk]))
        self.assertEqual(response.status_code, 403)

    def test_system_screens_remain_reachable(self):
        for name in ("accounts:user_list", "accounts:department_list",
                     "operations:setting_list", "operations:backup",
                     "audit:trail", "audit:integrity", "interop:interface_list",
                     "compliance:change_list", "operations:settings_index",
                     "compliance:password_change"):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_a_clinical_user_is_not_affected_by_the_barrier(self):
        scientist = make_user("sci", role=Role.SCIENTIST)
        self.client.force_login(scientist)
        self.assertEqual(self.client.get(reverse("laboratory:results")).status_code, 200)

    def test_settings_index_hides_laboratory_configuration_from_the_installer(self):
        from apps.accounts.context_processors import settings_index

        items = settings_index(self.installer)
        self.assertTrue(items)
        self.assertTrue(all(item.system for item in items))
        labels = {item.label for item in items}
        self.assertNotIn("Test definitions", labels)
        self.assertNotIn("Delta check rules", labels)
        self.assertIn("Users", labels)


class ProtectedAccountTests(TestCase):
    def setUp(self):
        self.installer = make_installer()
        self.admin = make_user("admin1", role=Role.ADMIN, password=PASSWORD)

    def test_installer_account_is_marked_protected(self):
        self.assertTrue(self.installer.is_protected_account)
        self.assertFalse(self.admin.is_protected_account)

    def test_installer_cannot_be_deleted(self):
        from apps.accounts.models import ProtectedAccountError

        allowed, reason = self.installer.may_be_deleted_by(self.admin)
        self.assertFalse(allowed)
        self.assertIn("permanent", reason)
        with self.assertRaises(ProtectedAccountError):
            self.installer.delete()

    def test_admin_cannot_reset_the_installer_password(self):
        allowed, reason = self.installer.may_have_password_reset_by(self.admin)
        self.assertFalse(allowed)
        self.assertIn("cannot be reset", reason)

    def test_installer_can_change_its_own_password(self):
        allowed, _ = self.installer.may_have_password_reset_by(self.installer)
        self.assertTrue(allowed)

    def test_reset_password_view_refuses_the_installer(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("accounts:user_reset_password", args=[self.installer.pk]), follow=True
        )
        self.assertContains(response, "cannot be reset")

    def test_delete_view_refuses_the_installer(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:user_delete", args=[self.installer.pk]), follow=True
        )
        self.assertContains(response, "permanent")
        self.assertTrue(User.objects.filter(pk=self.installer.pk).exists())

    def test_admin_can_disable_the_installer(self):
        """Disabling is the control a laboratory keeps over the installer."""
        self.client.force_login(self.admin)
        self.client.post(reverse("accounts:user_toggle_active", args=[self.installer.pk]))
        self.installer.refresh_from_db()
        self.assertFalse(self.installer.is_active)

    def test_a_disabled_account_cannot_sign_in(self):
        self.installer.is_active = False
        self.installer.save()
        self.client.logout()
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "installer", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200)  # re-rendered, not redirected

    def test_the_form_will_not_create_another_installer(self):
        from apps.accounts.forms import UserForm

        form = UserForm(data={"username": "sneaky", "name": "X", "role": Role.INSTALLER,
                              "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)


class AccountAdministrationTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin2", role=Role.ADMIN, password=PASSWORD)
        self.staff = make_user("tech9", role=Role.SCIENTIST, password=PASSWORD)
        self.client.force_login(self.admin)

    def test_admin_resets_a_password_and_forces_a_change(self):
        from apps.compliance.services import security_state

        response = self.client.post(
            reverse("accounts:user_reset_password", args=[self.staff.pk]),
            {"new_password": "Temp-Pass!456", "confirm_password": "Temp-Pass!456",
             "reason": "Forgotten password, identity confirmed in person."},
        )
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password("Temp-Pass!456"))
        self.assertTrue(security_state(self.staff).must_change_password)

    def test_password_reset_requires_a_reason_and_is_audited(self):
        response = self.client.post(
            reverse("accounts:user_reset_password", args=[self.staff.pk]),
            {"new_password": "Temp-Pass!456", "confirm_password": "Temp-Pass!456"},
        )
        self.assertEqual(response.status_code, 200)  # refused, reason missing

        self.client.post(
            reverse("accounts:user_reset_password", args=[self.staff.pk]),
            {"new_password": "Temp-Pass!456", "confirm_password": "Temp-Pass!456",
             "reason": "Locked out after leave."},
        )
        recorder.flush(timeout=5)
        event = AuditEvent.objects.filter(
            entity_type="accounts.User", entity_id=str(self.staff.pk)
        ).order_by("-sequence").first()
        self.assertIn("password reset", event.entity_label)
        self.assertEqual(event.reason, "Locked out after leave.")
        self.assertEqual(event.actor_username, "admin2")

    def test_mismatched_passwords_are_refused(self):
        response = self.client.post(
            reverse("accounts:user_reset_password", args=[self.staff.pk]),
            {"new_password": "Temp-Pass!456", "confirm_password": "Different!789",
             "reason": "x"},
        )
        self.assertEqual(response.status_code, 200)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.check_password("Temp-Pass!456"))

    def test_admin_disables_and_re_enables_an_account(self):
        self.client.post(reverse("accounts:user_toggle_active", args=[self.staff.pk]))
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)

        self.client.post(reverse("accounts:user_toggle_active", args=[self.staff.pk]))
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_admin_cannot_disable_their_own_account(self):
        self.client.post(reverse("accounts:user_toggle_active", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_deletes_an_account_with_no_records(self):
        self.client.post(reverse("accounts:user_delete", args=[self.staff.pk]))
        self.assertFalse(User.objects.filter(pk=self.staff.pk).exists())

    def test_an_account_that_has_signed_is_disabled_rather_than_deleted(self):
        """A signature must keep naming a real person."""
        from apps.compliance.services import apply_signature
        from apps.compliance.models import ElectronicSignature

        apply_signature(
            user=self.staff, meaning=ElectronicSignature.Meaning.REVIEW,
            entity_type="laboratory.Order", entity_id="o1",
            payload={"v": 1}, password=PASSWORD,
        )
        response = self.client.post(
            reverse("accounts:user_delete", args=[self.staff.pk]), follow=True
        )
        self.assertContains(response, "disabled instead")
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)

    def test_a_clinical_user_cannot_administer_accounts(self):
        self.client.force_login(self.staff)
        for name in ("accounts:user_list",):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        response = self.client.post(
            reverse("accounts:user_toggle_active", args=[self.admin.pk])
        )
        self.assertIn(response.status_code, (302, 403))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class SelfServicePasswordTests(TestCase):
    def test_every_role_can_change_its_own_password(self):
        for role in (Role.INSTALLER, Role.ADMIN, Role.MANAGER, Role.SCIENTIST,
                     Role.MEDIC, Role.CLERK, Role.PHLEBOTOMIST):
            with self.subTest(role=role):
                user = User.objects.create_user(
                    username=f"self-{role}", password=PASSWORD, name="X", role=role
                )
                self.client.force_login(user)
                self.assertEqual(
                    self.client.get(reverse("compliance:password_change")).status_code, 200
                )
                response = self.client.post(reverse("compliance:password_change"), {
                    "current_password": PASSWORD,
                    "new_password": "An0ther-Str0ng!99",
                    "confirm_password": "An0ther-Str0ng!99",
                })
                self.assertEqual(response.status_code, 302)
                user.refresh_from_db()
                self.assertTrue(user.check_password("An0ther-Str0ng!99"))


class CreateInstallerCommandTests(TestCase):
    def test_creates_an_installer_without_django_superuser_rights(self):
        call_command("create_installer", username="inst2", password=PASSWORD, verbosity=0)
        user = User.objects.get(username="inst2")
        self.assertEqual(user.role, Role.INSTALLER)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_refuses_a_duplicate_username(self):
        make_installer("inst3")
        with self.assertRaises(CommandError):
            call_command("create_installer", username="inst3", password=PASSWORD, verbosity=0)
