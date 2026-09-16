"""View-level tests: every route renders, and the workflow screens behave."""
from __future__ import annotations

from django.test import TestCase
from django.urls import NoReverseMatch, get_resolver, reverse

from apps.audit.recorder import recorder
from apps.common.constants import AuditAction, OrderStatus
from apps.laboratory.models import Order, Result
from apps.laboratory.services import create_order
from tests.factories import (
    grant_competency, make_department, make_order, make_patient, make_test,
    make_user, passing_qc,
)

PASSWORD = "Str0ng-Pass!23"

#: POST-only or side-effecting endpoints, exercised by the dedicated cases below.
NON_GET_ROUTES = {
    "accounts:logout", "audit:run_verification", "audit:acknowledge",
    "clinical:submit_epidemiology", "reporting:document_acknowledge",
    "billing:generate", "instrument_ingest",
    "instrument_host_query", "inbound_hl7",
    "compliance:subject_request_create",
    "accounts:lock_heartbeat", "accounts:lock_release",
}

#: Namespaces whose routes authenticate with a bearer token rather than a
#: session, so a logged-in browser is correctly refused. They are exercised by
#: tests/test_api.py instead.
TOKEN_AUTHENTICATED_NAMESPACES = ("api:",)


def all_url_names() -> list[str]:
    names: set[str] = set()

    def walk(patterns, namespace=None):
        for entry in patterns:
            if hasattr(entry, "url_patterns"):
                walk(entry.url_patterns, entry.namespace or namespace)
            elif entry.name:
                names.add(f"{namespace}:{entry.name}" if namespace else entry.name)

    walk(get_resolver().url_patterns)
    return sorted(names)


class RouteSmokeTests(TestCase):
    """Every GET route must render for an administrator.

    This is the cheapest guard against a template referencing a field that no
    longer exists — the kind of break that only shows up when a user opens the
    page.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin", role="admin", password=PASSWORD)
        cls.department = make_department()
        cls.test = make_test(department=cls.department)
        cls.patient = make_patient()
        cls.order = make_order(cls.patient, [cls.test])
        Result.objects.create(
            order=cls.order, test=cls.test, test_key=cls.test.id,
            value="5.0", entered_by="admin",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _args_for(self, name):
        mapping = {
            "audit:event_detail": None,  # resolved at call time
            "audit:entity_history": ["laboratory.Order", self.order.pk],
            "patients:detail": [self.patient.pk],
            "patients:update": [self.patient.pk],
            "patients:trend": [self.patient.pk],
            "laboratory:result_entry": [self.order.pk],
            "laboratory:test_update": [self.test.pk],
            "reporting:report_detail": [self.order.pk],
            "interop:fhir_report": [self.order.pk],
            "interop:hl7_oru": [self.order.pk],
        }
        if name == "audit:event_detail":
            from apps.audit.models import AuditEvent

            recorder.flush(timeout=5)
            event = AuditEvent.objects.order_by("sequence").first()
            return [event.sequence] if event else None
        return mapping.get(name)

    def test_every_get_route_renders(self):
        failures = []
        for name in all_url_names():
            if name in NON_GET_ROUTES or name.startswith(("admin:", "django-admin")):
                continue
            if name.startswith(TOKEN_AUTHENTICATED_NAMESPACES):
                continue
            args = self._args_for(name)
            try:
                url = reverse(name, args=args) if args else reverse(name)
            except NoReverseMatch:
                continue  # Route needs arguments this fixture does not provide.
            with self.subTest(route=name):
                response = self.client.get(url)
                if response.status_code not in (200, 302):
                    failures.append((name, url, response.status_code))
        self.assertEqual(failures, [], f"routes returned errors: {failures}")


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = make_user("tech", password=PASSWORD)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("operations:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response["Location"])

    def test_anonymous_api_request_gets_401_not_a_redirect(self):
        response = self.client.get("/api/some-endpoint/")
        self.assertEqual(response.status_code, 401)

    def test_login_succeeds_with_correct_credentials(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "tech", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 302)

    def test_login_fails_with_wrong_password(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "tech", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "correct username and password", status_code=200)


class RoleAccessTests(TestCase):
    """Role restrictions must hold at the view, not only in the navigation."""

    def setUp(self):
        self.clerk = make_user("clerk1", role="clerk", password=PASSWORD)
        self.manager = make_user("mgr1", role="manager", password=PASSWORD)

    def test_clerk_cannot_reach_user_administration(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 403)

    def test_clerk_cannot_reach_compliance_dashboard(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("compliance:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_manager_can_reach_compliance_dashboard(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("compliance:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_clerk_cannot_open_result_entry(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("laboratory:results"))
        self.assertEqual(response.status_code, 302)


class AccessioningViewTests(TestCase):
    def setUp(self):
        self.clerk = make_user("clerk2", role="clerk", password=PASSWORD)
        self.patient = make_patient()
        self.test = make_test()
        self.client.force_login(self.clerk)

    def test_accessioning_creates_an_order(self):
        response = self.client.post(reverse("laboratory:accessioning"), {
            "patient": self.patient.pk,
            "tests": [self.test.pk],
            "priority": "Routine",
            "ordered_by": "Dr Smith",
            "specimen_type": "Serum",
        })
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.patient, self.patient)
        self.assertTrue(order.accession_number)
        self.assertEqual(order.specimens.count(), 1)

    def test_accessioning_requires_at_least_one_test(self):
        response = self.client.post(reverse("laboratory:accessioning"), {
            "patient": self.patient.pk, "tests": [],
            "priority": "Routine", "ordered_by": "Dr Smith",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())


class ResultEntryViewTests(TestCase):
    def setUp(self):
        self.tech = make_user("tech2", password=PASSWORD)
        self.senior = make_user("senior2", role="manager", password=PASSWORD)
        self.test = make_test()
        self.patient = make_patient()
        self.order = create_order(patient=self.patient, tests=[self.test], ordered_by="Dr A")
        grant_competency(self.tech, test=self.test)
        grant_competency(self.senior, test=self.test)
        passing_qc(self.test)

    def test_entering_a_result_saves_it(self):
        self.client.force_login(self.tech)
        response = self.client.post(
            reverse("laboratory:result_entry", args=[self.order.pk]),
            {f"result_{self.test.id}": "5.4", "action": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Result.objects.get(order=self.order, test_key=self.test.id).value, "5.4")

    def test_verification_without_password_shows_the_control_message(self):
        self.client.force_login(self.tech)
        self.client.post(reverse("laboratory:result_entry", args=[self.order.pk]),
                         {f"result_{self.test.id}": "5.4", "action": ""})

        self.client.force_login(self.senior)
        response = self.client.post(
            reverse("laboratory:result_entry", args=[self.order.pk]),
            {f"result_{self.test.id}": "5.4", "action": AuditAction.CLINICAL_VERIFY},
            follow=True,
        )
        self.assertContains(response, "password is required")
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, OrderStatus.COMPLETED)

    def test_verification_with_password_completes_the_order(self):
        self.client.force_login(self.tech)
        self.client.post(reverse("laboratory:result_entry", args=[self.order.pk]),
                         {f"result_{self.test.id}": "5.4", "action": ""})

        self.client.force_login(self.senior)
        self.client.post(reverse("laboratory:result_entry", args=[self.order.pk]), {
            f"result_{self.test.id}": "5.4",
            "action": AuditAction.CLINICAL_VERIFY,
            "password": PASSWORD,
        })
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)


class AuditViewTests(TestCase):
    def setUp(self):
        self.manager = make_user("mgr2", role="manager", password=PASSWORD)
        self.client.force_login(self.manager)
        recorder.flush(timeout=5)

    def test_trail_lists_events(self):
        response = self.client.get(reverse("audit:trail"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit trail")

    def test_verification_can_be_run_from_the_ui(self):
        response = self.client.post(reverse("audit:run_verification"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chain")

    def test_csv_export_returns_a_file(self):
        response = self.client.get(reverse("audit:export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_verify_api_reports_chain_state(self):
        response = self.client.get(reverse("audit:verify_api"))
        self.assertIn(response.status_code, (200, 409))
        self.assertIn("ok", response.json())
