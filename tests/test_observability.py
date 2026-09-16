"""Metrics, readiness and structured logging.

The point of the redaction test is that a metrics endpoint is the one place in
this system nobody expects to find patient data, which is exactly why it is
worth asserting that none leaks there.
"""
from __future__ import annotations

import json
import logging

from django.test import TestCase, override_settings

from apps.operations import continuity
from apps.operations.exceptions import ExceptionSource, raise_exception
from apps.operations.models import ExceptionItem
from apps.operations.observability import JsonFormatter, collect
from tests.factories import make_order, make_patient, make_test, make_user


class MetricsTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test], accession="2026-09-16-0007")

    def test_the_endpoint_is_prometheus_text(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response["Content-Type"])
        body = response.content.decode()
        self.assertIn("# HELP dx_audit_recorder_running", body)
        self.assertIn("# TYPE dx_audit_recorder_running gauge", body)

    def test_it_reports_the_audit_recorder(self):
        self.assertIn("dx_audit_recorder_running", collect())
        self.assertIn("dx_audit_queue_depth", collect())

    def test_it_counts_orders_by_status(self):
        body = collect()
        self.assertIn('dx_orders{status="Pending"} 1', body)

    def test_it_counts_open_exceptions_by_severity(self):
        raise_exception(
            source=ExceptionSource.MANUAL, source_key="k1", title="Something",
            severity=ExceptionItem.Severity.CRITICAL,
        )
        self.assertIn('dx_exceptions_open{severity="critical"} 1', collect())

    def test_it_reports_read_only_mode(self):
        self.assertIn("dx_read_only_mode 0", collect())
        continuity.set_read_only("Restoring", user=make_user("mgr", role="manager"))
        self.assertIn("dx_read_only_mode 1", collect())

    def test_it_reports_downtime_pack_age_as_minus_one_when_there_is_none(self):
        self.assertIn("dx_downtime_pack_age_seconds -1", collect())

    def test_no_identifier_reaches_the_metrics(self):
        """Counts and states, never identifiers."""
        body = collect()
        for identifier in ("2026-09-16-0007", self.patient.mrn, "Jane", "Doe",
                           str(self.patient.pk), str(self.order.pk)):
            self.assertNotIn(identifier, body)

    @override_settings(METRICS_TOKEN="sekrit")
    def test_a_token_can_be_required(self):
        self.assertEqual(self.client.get("/metrics").status_code, 401)
        self.assertEqual(
            self.client.get("/metrics", HTTP_AUTHORIZATION="Bearer sekrit").status_code,
            200,
        )

    @override_settings(METRICS_TOKEN="sekrit")
    def test_a_wrong_token_is_refused(self):
        response = self.client.get("/metrics", HTTP_AUTHORIZATION="Bearer wrong")
        self.assertEqual(response.status_code, 401)

    def test_a_collection_failure_does_not_take_the_endpoint_down(self):
        from unittest.mock import patch

        with patch("apps.operations.observability.collect", side_effect=RuntimeError):
            response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 500)
        self.assertIn("collection failed", response.content.decode())

    def test_label_values_are_escaped(self):
        """A crafted status must not be able to break the exposition format."""
        from apps.operations.observability import _metric

        rendered = _metric("x", 1, help_text="h", labels={"k": 'a"b\\c'})
        self.assertIn(r'k="a\"b\\c"', rendered)


class ReadinessTests(TestCase):
    def test_ready_when_everything_is_up(self):
        response = self.client.get("/readyz/")
        body = response.json()
        self.assertIn("database", body["checks"])
        self.assertTrue(body["checks"]["database"])

    def test_it_reports_the_audit_immutability_triggers(self):
        """The test runner drops them, so this asserts the check runs at all."""
        body = self.client.get("/readyz/").json()
        self.assertIn("audit_immutability", body["checks"])

    def test_not_ready_returns_503_so_a_balancer_stops_sending_traffic(self):
        from unittest.mock import patch

        with patch("apps.audit.recorder.recorder.is_running", return_value=False):
            response = self.client.get("/readyz/")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ready"])

    def test_readiness_needs_no_session(self):
        response = self.client.get("/readyz/")
        self.assertNotEqual(response.status_code, 302)


class JsonLoggingTests(TestCase):
    def _line(self, record) -> dict:
        return json.loads(JsonFormatter().format(record))

    def _record(self, message="hello") -> logging.LogRecord:
        return logging.LogRecord(
            name="dx.test", level=logging.INFO, pathname=__file__, lineno=1,
            msg=message, args=(), exc_info=None,
        )

    def test_a_line_is_one_json_object(self):
        payload = self._line(self._record())
        self.assertEqual(payload["message"], "hello")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "dx.test")
        self.assertIn("time", payload)

    def test_the_request_id_is_carried_so_logs_join_to_the_audit_trail(self):
        from apps.audit.context import audit_as

        with audit_as(request_id="req-123", actor_username="jsmith"):
            payload = self._line(self._record())

        self.assertEqual(payload["request_id"], "req-123")
        self.assertEqual(payload["actor"], "jsmith")

    def test_an_exception_is_included(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = self._record()
            record.exc_info = sys.exc_info()
            payload = self._line(record)
        self.assertIn("ValueError: boom", payload["exception"])

    def test_formatting_never_raises(self):
        """Logging that can throw turns a small fault into an outage."""
        from unittest.mock import patch

        with patch("apps.audit.context.get_context", side_effect=RuntimeError):
            payload = self._line(self._record())
        self.assertEqual(payload["message"], "hello")
