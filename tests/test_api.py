"""The public API, its scoping, and webhook delivery.

The scope tests are the important ones. An API is the easiest way to turn a
carefully-controlled system into an uncontrolled one: the screens enforce
roles, and then a token with every scope is issued to a contractor and none of
that matters any more.
"""
from __future__ import annotations

import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.api.models import ApiClient, Scope, Webhook, WebhookDelivery
from apps.api.webhooks import deliver, emit, redact, sign, verify
from apps.compliance.models import PHIAccessLog
from apps.interop.models import Icd10Code
from tests.factories import make_order, make_patient, make_test


def issue(*scopes, **fields):
    client, token = ApiClient.issue(
        name=fields.pop("name", "Ward dashboard"),
        organisation=fields.pop("organisation", "St Elsewhere"),
        purpose=fields.pop("purpose", "Displaying results on the ward"),
        scopes=list(scopes),
        **fields,
    )
    return client, token


class AuthenticationTests(TestCase):
    def setUp(self):
        self.client_record, self.token = issue(Scope.CATALOGUE_READ)

    def _get(self, url, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token or self.token}"} if token is not False else {}
        return self.client.get(url, **headers)

    def test_a_valid_token_is_accepted(self):
        response = self._get("/api/v1/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["client"]["name"], "Ward dashboard")

    def test_no_token_is_refused(self):
        response = self._get("/api/v1/", token=False)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "unauthenticated")

    def test_a_wrong_secret_is_refused(self):
        key_id = self.token.split(".")[0]
        response = self._get("/api/v1/", token=f"{key_id}.wrong")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "invalid_credentials")

    def test_an_unknown_key_id_is_refused_the_same_way(self):
        """A wrong key and a wrong secret must be indistinguishable."""
        response = self._get("/api/v1/", token="deadbeefdeadbeef.whatever")
        self.assertEqual(response.json()["error"]["code"], "invalid_credentials")

    def test_a_malformed_token_is_refused(self):
        response = self._get("/api/v1/", token="no-dot-here")
        self.assertEqual(response.json()["error"]["code"], "malformed_token")

    def test_a_disabled_client_is_refused(self):
        self.client_record.active = False
        self.client_record.save(update_fields=["active"])
        response = self._get("/api/v1/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "client_disabled")

    def test_an_expired_client_is_refused(self):
        from django.utils import timezone
        from datetime import timedelta

        self.client_record.expires_at = timezone.now() - timedelta(days=1)
        self.client_record.save(update_fields=["expires_at"])
        response = self._get("/api/v1/")
        self.assertEqual(response.json()["error"]["code"], "client_expired")

    def test_the_secret_is_not_stored_in_recoverable_form(self):
        self.assertNotIn(self.token.split(".", 1)[1], self.client_record.secret_hash)
        self.assertTrue(self.client_record.verify(self.token.split(".", 1)[1]))

    def test_rotating_invalidates_the_old_secret(self):
        old = self.token
        new = self.client_record.rotate_secret()
        self.assertEqual(self._get("/api/v1/", token=old).status_code, 401)
        self.assertEqual(self._get("/api/v1/", token=new).status_code, 200)


class ScopeTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])

    def _get(self, url, token):
        return self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_catalogue_scope_cannot_read_patients(self):
        _, token = issue(Scope.CATALOGUE_READ)
        response = self._get("/api/v1/patients/", token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "insufficient_scope")

    def test_patient_scope_can_read_patients(self):
        _, token = issue(Scope.PATIENTS_READ)
        response = self._get("/api/v1/patients/", token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["mrn"], "MRN001")

    def test_order_scope_does_not_grant_result_reads(self):
        _, token = issue(Scope.ORDERS_READ)
        response = self._get(f"/api/v1/orders/{self.order.pk}/results/", token)
        self.assertEqual(response.status_code, 403)

    def test_the_error_names_the_missing_scope(self):
        _, token = issue(Scope.CATALOGUE_READ)
        body = self._get("/api/v1/orders/", token).json()
        self.assertIn("orders:read", body["error"]["required"])


class PhiLoggingTests(TestCase):
    def test_a_successful_patient_read_is_recorded_as_a_disclosure(self):
        patient = make_patient()
        client_record, token = issue(Scope.PATIENTS_READ)

        self.client.get(
            f"/api/v1/patients/{patient.pk}/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )

        entry = PHIAccessLog.objects.get()
        self.assertEqual(entry.username, f"api:{client_record.name}")
        self.assertEqual(entry.patient_id, patient.pk)
        self.assertIn("St Elsewhere", entry.justification)

    def test_a_miss_is_not_recorded(self):
        """Recording a 404 would make the log itself a way to probe for patients."""
        _, token = issue(Scope.PATIENTS_READ)
        self.client.get(
            "/api/v1/patients/does-not-exist/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(PHIAccessLog.objects.count(), 0)


class CollectionTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test])
        _, self.token = issue(
            Scope.CATALOGUE_READ, Scope.ORDERS_READ, Scope.ORDERS_WRITE,
            Scope.PATIENTS_READ, Scope.PATIENTS_WRITE, Scope.RESULTS_READ,
            Scope.REPORTS_READ,
        )

    def _get(self, url):
        return self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def _post(self, url, payload):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_collections_are_paginated(self):
        body = self._get("/api/v1/tests/?page_size=1").json()
        self.assertEqual(len(body["data"]), 1)
        self.assertIn("total_items", body["page"])

    def test_an_out_of_range_page_returns_an_empty_list_not_an_error(self):
        body = self._get("/api/v1/tests/?page=99").json()
        self.assertEqual(body["data"], [])
        self.assertFalse(body["page"]["has_next"])

    def test_registering_the_same_mrn_twice_is_not_an_error(self):
        payload = {"mrn": "MRN999", "first_name": "A", "last_name": "B",
                   "date_of_birth": "1990-01-01"}
        first = self._post("/api/v1/patients/new/", payload)
        second = self._post("/api/v1/patients/new/", payload)

        self.assertEqual(first.status_code, 201)
        self.assertTrue(first.json()["created"])
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])

    def test_placing_an_order_with_an_unknown_test_changes_nothing(self):
        from apps.laboratory.models import Order

        before = Order.objects.count()
        response = self._post("/api/v1/orders/new/", {
            "mrn": self.patient.mrn, "tests": ["GLU", "NOPE"],
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "unknown_tests")
        self.assertEqual(Order.objects.count(), before)

    def test_placing_an_order_works(self):
        response = self._post("/api/v1/orders/new/", {
            "mrn": self.patient.mrn, "tests": ["GLU"], "priority": "STAT",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["priority"], "STAT")

    def test_an_order_can_carry_icd10_diagnoses(self):
        Icd10Code.objects.create(code="E11.9", description="Type 2 diabetes mellitus")
        response = self._post("/api/v1/orders/new/", {
            "mrn": self.patient.mrn, "tests": ["GLU"],
            "diagnoses": [{"code": "E11.9"}],
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["diagnoses"][0]["code"], "E11.9")

    def test_an_unknown_diagnosis_is_refused(self):
        response = self._post("/api/v1/orders/new/", {
            "mrn": self.patient.mrn, "tests": ["GLU"], "diagnoses": [{"code": "ZZ9"}],
        })
        self.assertEqual(response.json()["error"]["code"], "unknown_diagnosis")

    def test_a_report_can_be_rendered_as_fhir(self):
        response = self._get(f"/api/v1/orders/{self.order.pk}/report/?format=fhir")
        self.assertEqual(response.json()["resourceType"], "Bundle")

    def test_a_report_can_be_rendered_as_hl7(self):
        response = self._get(f"/api/v1/orders/{self.order.pk}/report/?format=hl7")
        self.assertIn("MSH|", response.content.decode())

    def test_an_unknown_format_is_refused(self):
        response = self._get(f"/api/v1/orders/{self.order.pk}/report/?format=xml")
        self.assertEqual(response.json()["error"]["code"], "invalid_format")

    def test_invalid_json_is_reported_clearly(self):
        response = self.client.post(
            "/api/v1/orders/new/", data="{not json", content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.json()["error"]["code"], "invalid_json")


class RateLimitTests(TestCase):
    def test_a_client_over_its_limit_is_refused(self):
        _, token = issue(Scope.CATALOGUE_READ, rate_limit_per_minute=2)
        for _ in range(2):
            self.assertEqual(
                self.client.get("/api/v1/", HTTP_AUTHORIZATION=f"Bearer {token}").status_code,
                200,
            )
        response = self.client.get("/api/v1/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "rate_limited")


class WebhookSignatureTests(TestCase):
    def test_a_signature_verifies_against_the_shared_secret(self):
        body = b'{"event":"order.created"}'
        header = sign("s3cret", body)
        self.assertTrue(verify("s3cret", body, header))

    def test_a_tampered_body_fails(self):
        header = sign("s3cret", b'{"a":1}')
        self.assertFalse(verify("s3cret", b'{"a":2}', header))

    def test_the_wrong_secret_fails(self):
        body = b'{"a":1}'
        self.assertFalse(verify("other", body, sign("s3cret", body)))

    def test_an_old_signature_is_rejected(self):
        import time

        body = b'{"a":1}'
        header = sign("s3cret", body, timestamp=int(time.time()) - 3600)
        self.assertFalse(verify("s3cret", body, header))


class WebhookDeliveryTests(TestCase):
    def setUp(self):
        self.webhook = Webhook.objects.create(
            name="Ward", url="https://example.invalid/hook",
            events=["order.created", "result.verified"],
        )

    def test_identifiers_are_stripped_by_default(self):
        payload = {"patient": {"id": "abc", "mrn": "MRN001", "first_name": "Jane"}}
        stripped = redact(payload)
        self.assertEqual(stripped["patient"]["id"], "abc")
        self.assertEqual(stripped["patient"]["mrn"], "[redacted]")
        self.assertEqual(stripped["patient"]["first_name"], "[redacted]")

    def _emit(self, event, payload=None):
        """Emit and run the on-commit hook.

        ``emit`` defers the delivery rows to ``transaction.on_commit`` so a
        rolled-back result never produces a webhook saying it happened — which
        means a test has to drive the commit hooks explicitly.
        """
        with self.captureOnCommitCallbacks(execute=True):
            emit(event, payload or {})

    def test_emit_queues_one_delivery_per_subscriber(self):
        self._emit("order.created", {"order_id": "1"})
        self.assertEqual(WebhookDelivery.objects.count(), 1)

    def test_an_unsubscribed_event_queues_nothing(self):
        self._emit("qc.failed")
        self.assertEqual(WebhookDelivery.objects.count(), 0)

    def test_a_disabled_webhook_receives_nothing(self):
        self.webhook.active = False
        self.webhook.save(update_fields=["active"])
        self._emit("order.created")
        self.assertEqual(WebhookDelivery.objects.count(), 0)

    def test_a_failed_delivery_is_retried_with_backoff(self):
        self._emit("order.created", {"order_id": "1"})
        delivery = WebhookDelivery.objects.get()

        with patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            self.assertFalse(deliver(delivery))

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.Status.RETRYING)
        self.assertEqual(delivery.attempts, 1)

    def test_delivery_gives_up_after_the_attempt_limit(self):
        self._emit("order.created", {"order_id": "1"})
        delivery = WebhookDelivery.objects.get()
        delivery.attempts = WebhookDelivery.MAX_ATTEMPTS - 1
        delivery.save(update_fields=["attempts"])

        with patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            deliver(delivery)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.Status.FAILED)

    def test_a_persistently_failing_subscriber_is_disabled(self):
        self.webhook.consecutive_failures = 19
        self.webhook.save(update_fields=["consecutive_failures"])
        self._emit("order.created")
        delivery = WebhookDelivery.objects.get()

        with patch("urllib.request.urlopen", side_effect=OSError("gone")):
            deliver(delivery)

        self.webhook.refresh_from_db()
        self.assertFalse(self.webhook.active)
        self.assertIn("consecutive delivery failures", self.webhook.disabled_reason)

    def test_the_payload_carries_a_signature_header(self):
        self._emit("order.created", {"order_id": "1"})
        delivery = WebhookDelivery.objects.get()
        captured = {}

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def capture(request, timeout=None):
            captured["headers"] = dict(request.headers)
            captured["body"] = request.data
            return Response()

        with patch("urllib.request.urlopen", side_effect=capture):
            self.assertTrue(deliver(delivery))

        header = captured["headers"]["X-dx-signature"]
        self.assertTrue(verify(self.webhook.secret, captured["body"], header))
        self.assertEqual(captured["headers"]["X-dx-event"], "order.created")


class ManagementScreenTests(TestCase):
    def test_only_an_administrator_can_issue_a_credential(self):
        from tests.factories import make_user

        manager = make_user("mgr", role="manager", password="Str0ng-Pass!23")
        self.client.force_login(manager)
        response = self.client.get(reverse("integrations:client_list"))
        self.assertEqual(response.status_code, 403)

    def test_an_administrator_sees_the_secret_once(self):
        from tests.factories import make_user

        admin = make_user("admin1", role="admin", password="Str0ng-Pass!23")
        self.client.force_login(admin)
        response = self.client.post(reverse("integrations:client_create"), {
            "name": "Research extract",
            "organisation": "University",
            "purpose": "Approved study 123",
            "scopes": [Scope.CATALOGUE_READ],
            "rate_limit_per_minute": 60,
            "active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Copy this now")


class DeploymentCheckTests(TestCase):
    """The checks that stop a silently-ineffective rate limit reaching production."""

    def test_a_per_process_cache_is_flagged_outside_debug(self):
        from apps.api.checks import rate_limiter_needs_a_shared_cache

        with self.settings(
            DEBUG=False,
            CACHES={"default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache"
            }},
        ):
            warnings = rate_limiter_needs_a_shared_cache(None)
        self.assertEqual([w.id for w in warnings], ["dx.W001"])

    def test_a_shared_cache_passes(self):
        from apps.api.checks import rate_limiter_needs_a_shared_cache

        with self.settings(
            DEBUG=False,
            CACHES={"default": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "LOCATION": "dx_cache",
            }},
        ):
            self.assertEqual(rate_limiter_needs_a_shared_cache(None), [])

    def test_development_is_not_nagged(self):
        from apps.api.checks import rate_limiter_needs_a_shared_cache

        with self.settings(DEBUG=True):
            self.assertEqual(rate_limiter_needs_a_shared_cache(None), [])

    def test_an_audit_spool_on_tmp_is_flagged(self):
        from apps.api.checks import audit_spool_must_be_durable

        with self.settings(DEBUG=False, AUDIT_SPOOL_FILE="/tmp/audit-spool.jsonl"):
            warnings = audit_spool_must_be_durable(None)
        self.assertEqual([w.id for w in warnings], ["dx.W002"])

    def test_a_durable_audit_spool_passes(self):
        from apps.api.checks import audit_spool_must_be_durable

        with self.settings(DEBUG=False, AUDIT_SPOOL_FILE="/var/lib/dx/audit-spool.jsonl"):
            self.assertEqual(audit_spool_must_be_durable(None), [])
