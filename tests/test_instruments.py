"""Instrument interface: protocol framing, parsing and the ingest endpoint."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "instrument_server"))

from dx_instrument.parser import parse_astm, parse_hl7  # noqa: E402
from dx_instrument.protocol import (  # noqa: E402
    build_astm_frame, extract_mllp, verify_astm_frame, wrap_mllp,
)

from apps.interop.models import InstrumentInterface, InstrumentMessage  # noqa: E402
from apps.laboratory.models import Result  # noqa: E402
from apps.laboratory.services import create_order  # noqa: E402
from tests.factories import make_patient, make_test  # noqa: E402

TOKEN = "test-ingest-token"


class AstmProtocolTests(TestCase):
    def test_frame_round_trips(self):
        frame = build_astm_frame(1, "R|1|^^^GLU|5.4|mmol/L||N||F\r")
        valid, text = verify_astm_frame(frame)
        self.assertTrue(valid)
        self.assertEqual(text, "R|1|^^^GLU|5.4|mmol/L||N||F\r")

    def test_corrupted_frame_is_rejected(self):
        """A bad checksum must not yield a parsed result."""
        frame = build_astm_frame(1, "R|1|^^^GLU|5.4|mmol/L||N||F\r")
        corrupted = frame[:6] + b"X" + frame[7:]
        valid, _ = verify_astm_frame(corrupted)
        self.assertFalse(valid)

    def test_truncated_frame_is_rejected(self):
        self.assertFalse(verify_astm_frame(b"\x02garbage")[0])


class MllpProtocolTests(TestCase):
    def test_complete_block_is_extracted(self):
        messages, remainder = extract_mllp(wrap_mllp("MSH|^~\\&|A|B\r"))
        self.assertEqual(messages, ["MSH|^~\\&|A|B\r"])
        self.assertEqual(remainder, b"")

    def test_partial_block_is_retained_for_more_data(self):
        messages, remainder = extract_mllp(b"\x0bMSH|partial")
        self.assertEqual(messages, [])
        self.assertTrue(remainder.startswith(b"\x0b"))

    def test_two_blocks_in_one_buffer(self):
        buffer = wrap_mllp("MSH|1\r") + wrap_mllp("MSH|2\r")
        messages, remainder = extract_mllp(buffer)
        self.assertEqual(len(messages), 2)
        self.assertEqual(remainder, b"")


class ParserTests(TestCase):
    def test_astm_message_is_parsed(self):
        payload = "\r".join([
            "H|\\^&|||ARCH-1^1.0|||||||P|1394-97|20260102101500",
            "P|1|||MRN-1||||U",
            "O|1|2026-01-02-0001|2026-01-02-0001||R|20260102101500",
            "R|1|^^^GLU|5.4|mmol/L||N||F||ARCH-1|20260102101500|20260102101500",
            "R|2|^^^NA|139|mmol/L||N||F||ARCH-1|20260102101500|20260102101500",
            "L|1|N",
        ])
        parsed = parse_astm(payload)
        self.assertEqual(parsed.accession, "2026-01-02-0001")
        self.assertEqual(parsed.instrument, "ARCH-1")
        self.assertEqual(len(parsed.results), 2)
        self.assertEqual(parsed.results[0]["test_code"], "GLU")
        self.assertEqual(parsed.results[0]["value"], "5.4")

    def test_hl7_message_is_parsed(self):
        payload = "\r".join([
            "MSH|^~\\&|ARCH-1|LAB|DX|LAB|20260102101500||ORU^R01|MSG1|P|2.5",
            "PID|1||MRN-1||DOE^JOHN||19700101|M",
            "OBR|1|PLACER1|2026-01-02-0001|^Panel|||20260102101500",
            "OBX|1|NM|GLU^Glucose^^GLU|1|5.4|mmol/L|||||F|||20260102101500",
        ])
        parsed = parse_hl7(payload)
        self.assertEqual(parsed.accession, "2026-01-02-0001")
        self.assertEqual(len(parsed.results), 1)
        self.assertEqual(parsed.results[0]["test_code"], "GLU")

    def test_malformed_records_are_skipped_not_fatal(self):
        parsed = parse_astm("H|\rnonsense\rR|1\rL|1|N")
        self.assertEqual(parsed.results, [])


@override_settings(INSTRUMENT_INGEST_TOKEN=TOKEN)
class IngestEndpointTests(TestCase):
    def setUp(self):
        self.test = make_test(code="GLU")
        self.patient = make_patient()
        self.order = create_order(patient=self.patient, tests=[self.test], ordered_by="Dr A")
        self.interface = InstrumentInterface.objects.create(name="ARCH-1", protocol="astm")
        self.url = reverse("instrument_ingest")

    def _post(self, payload, token=TOKEN):
        return self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )

    def test_results_are_applied(self):
        response = self._post({
            "interface_id": self.interface.pk,
            "accession": self.order.accession_number,
            "results": [{"test_code": "GLU", "value": "5.4"}],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["applied"], 1)
        result = Result.objects.get(order=self.order, test_key=self.test.id)
        self.assertEqual(result.value, "5.4")
        self.assertEqual(result.entered_by, "instrument:ARCH-1")

    def test_missing_token_is_rejected(self):
        response = self.client.post(
            self.url, data=json.dumps({"accession": "x", "results": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_wrong_token_is_rejected(self):
        response = self._post({"accession": "x", "results": []}, token="wrong")
        self.assertEqual(response.status_code, 401)

    def test_unknown_accession_is_reported_not_silently_dropped(self):
        response = self._post({"accession": "no-such-accession",
                               "results": [{"test_code": "GLU", "value": "5.4"}]})
        self.assertEqual(response.status_code, 422)
        self.assertIn("No order matching", response.json()["errors"][0])

    def test_unknown_test_code_is_reported(self):
        response = self._post({
            "interface_id": self.interface.pk,
            "accession": self.order.accession_number,
            "results": [{"test_code": "NOPE", "value": "1"}],
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn("Unknown test code NOPE", response.json()["errors"][0])

    def test_invalid_json_is_recorded_for_troubleshooting(self):
        response = self.client.post(
            self.url, data="{not json", content_type="application/json",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(InstrumentMessage.objects.filter(status="Failed").exists())

    def test_raw_payload_is_retained(self):
        self._post({
            "interface_id": self.interface.pk,
            "accession": self.order.accession_number,
            "results": [{"test_code": "GLU", "value": "5.4"}],
        })
        message = InstrumentMessage.objects.get()
        self.assertEqual(message.status, InstrumentMessage.Status.APPLIED)
        self.assertEqual(message.results_applied, 1)
        self.assertIn("GLU", message.raw_payload)

    def test_instrument_code_map_is_applied(self):
        self.interface.test_code_map = {"0001": "GLU"}
        self.interface.save()
        response = self._post({
            "interface_id": self.interface.pk,
            "accession": self.order.accession_number,
            "results": [{"test_code": "0001", "value": "6.1"}],
        })
        self.assertEqual(response.json()["applied"], 1)

    def test_instrument_results_are_attributed_in_the_audit_trail(self):
        from apps.audit.models import AuditEvent
        from apps.audit.recorder import recorder

        self._post({
            "interface_id": self.interface.pk,
            "accession": self.order.accession_number,
            "results": [{"test_code": "GLU", "value": "5.4"}],
        })
        recorder.flush(timeout=5)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor_username="instrument:ARCH-1", source="instrument"
            ).exists()
        )

    def test_critical_instrument_result_raises_a_notification(self):
        from apps.clinical.models import CriticalValueNotification

        self._post({
            "interface_id": self.interface.pk,
            "accession": self.order.accession_number,
            "results": [{"test_code": "GLU", "value": "30.0"}],
        })
        self.assertTrue(
            CriticalValueNotification.objects.filter(order=self.order).exists(),
            "an instrument result outside the panic limit must raise a notification",
        )


class QueryParsingTests(TestCase):
    """The analyser asking what to run, rather than reporting what it found."""

    def test_an_astm_query_record_is_recognised(self):
        message = parse_astm(
            "H|\\^&|||ARCH-1|||||||P|1\r"
            "Q|1|^2026-01-01-0001^|||||||||O\r"
            "L|1|N\r"
        )
        self.assertTrue(message.is_query)
        self.assertEqual(message.queries, ["2026-01-01-0001"])
        self.assertTrue(message.is_empty)

    def test_a_result_message_is_not_a_query(self):
        message = parse_astm(
            "H|\\^&|||ARCH-1|||||||P|1\r"
            "O|1|2026-01-01-0001||^^^GLU\r"
            "R|1|^^^GLU|5.4|mmol/L||N||F\r"
        )
        self.assertFalse(message.is_query)
        self.assertEqual(len(message.results), 1)

    def test_an_hl7_qpd_segment_is_recognised(self):
        message = parse_hl7(
            "MSH|^~\\&|ARCH|LAB|DX|LAB|20260101120000||QBP^Q11|MSG1|P|2.5\r"
            "QPD|SLI^Specimen labelling instructions|Q1|2026-01-01-0001\r"
            "RCP|I\r"
        )
        self.assertTrue(message.is_query)
        self.assertEqual(message.queries, ["2026-01-01-0001"])

    def test_several_specimens_can_be_queried_in_one_message(self):
        message = parse_astm(
            "H|\\^&|||ARCH-1|||||||P|1\r"
            "Q|1|^TUBE-1^|||||||||O\r"
            "Q|2|^TUBE-2^|||||||||O\r"
            "L|1|N\r"
        )
        self.assertEqual(message.queries, ["TUBE-1", "TUBE-2"])
