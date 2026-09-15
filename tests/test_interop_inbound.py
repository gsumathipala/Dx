"""Inbound HL7 (orders and patient administration) and host query mode."""
from __future__ import annotations

import json
from datetime import date

from django.test import TestCase, override_settings

from apps.common.constants import OrderStatus
from apps.interop import inbound
from apps.interop.models import HostQuery, Icd10Code, InstrumentInterface
from apps.interop.query import outstanding_tests, resolve_order
from apps.laboratory.models import Order, OrderDiagnosis, Result, Specimen
from apps.patients.models import Patient
from tests.factories import make_order, make_patient, make_test

TOKEN = "test-ingest-token"


def msh(message_type: str, control_id: str = "MSG0001") -> str:
    return f"MSH|^~\\&|HIS|HOSP|DX|LAB|20260101120000||{message_type}|{control_id}|P|2.5"


def pid(mrn="MRN900", family="Smith", given="John", dob="19800101", sex="M") -> str:
    return f"PID|1||{mrn}^^^HOSP^MR||{family}^{given}||{dob}|{sex}|||1 High Street^^Town^^AB1 2CD||01234 567890"


class MessageParsingTests(TestCase):
    def test_a_message_must_start_with_msh(self):
        with self.assertRaises(inbound.MalformedMessage):
            inbound.parse_message("PID|1||MRN1")

    def test_an_empty_message_is_malformed(self):
        with self.assertRaises(inbound.MalformedMessage):
            inbound.parse_message("   ")

    def test_escaped_delimiters_are_restored(self):
        message = inbound.parse_message(msh("ADT^A28") + "\r" + pid(family="O\\S\\Brien"))
        self.assertEqual(message.first("PID").get(5, 1), "O^Brien")

    def test_timestamps_of_each_supported_precision_parse(self):
        self.assertEqual(inbound.parse_hl7_date("19800101"), date(1980, 1, 1))
        self.assertEqual(inbound.parse_hl7_date("198001011230"), date(1980, 1, 1))
        self.assertEqual(inbound.parse_hl7_date("19800101123045"), date(1980, 1, 1))
        self.assertIsNone(inbound.parse_hl7_date(""))
        self.assertIsNone(inbound.parse_hl7_date("nonsense"))

    def test_a_zone_offset_is_ignored_rather_than_breaking_the_parse(self):
        self.assertEqual(inbound.parse_hl7_date("19800101+0100"), date(1980, 1, 1))


class AdtTests(TestCase):
    def test_a28_registers_a_patient(self):
        code, detail = inbound.handle(msh("ADT^A28") + "\r" + pid())
        self.assertEqual(code, "AA")
        self.assertEqual(detail["action"], "created")

        patient = Patient.objects.get(mrn="MRN900")
        self.assertEqual(patient.last_name, "Smith")
        self.assertEqual(patient.first_name, "John")
        self.assertEqual(patient.dob, date(1980, 1, 1))

    def test_a08_updates_demographics(self):
        inbound.handle(msh("ADT^A28") + "\r" + pid())
        code, detail = inbound.handle(
            msh("ADT^A08", "MSG2") + "\r" + pid(family="Smythe")
        )
        self.assertEqual(code, "AA")
        self.assertIn("last_name", detail["fields"])
        self.assertEqual(Patient.objects.get(mrn="MRN900").last_name, "Smythe")

    def test_a_patient_without_a_date_of_birth_is_refused(self):
        """Age drives reference intervals; guessing it would degrade them silently."""
        code, detail = inbound.handle(msh("ADT^A28") + "\r" + pid(dob=""))
        self.assertEqual(code, "AE")
        self.assertIn("date of birth", detail["error"])

    def test_a_patient_without_an_mrn_is_refused(self):
        segment = "PID|1||||Smith^John||19800101|M"
        code, detail = inbound.handle(msh("ADT^A28") + "\r" + segment)
        self.assertEqual(code, "AE")
        self.assertIn("medical record number", detail["error"])

    def test_an_unsupported_trigger_is_refused_not_ignored(self):
        code, _ = inbound.handle(msh("ADT^A03") + "\r" + pid())
        self.assertEqual(code, "AE")

    def test_a40_merges_and_retains_the_old_record(self):
        inbound.handle(msh("ADT^A28") + "\r" + pid(mrn="OLD1"))
        inbound.handle(msh("ADT^A28", "M2") + "\r" + pid(mrn="NEW1"))

        old = Patient.objects.get(mrn="OLD1")
        order = make_order(old, [])

        code, detail = inbound.handle(
            msh("ADT^A40", "M3") + "\r" + pid(mrn="NEW1") + "\r" + "MRG|OLD1"
        )

        self.assertEqual(code, "AA")
        self.assertEqual(detail["orders_moved"], 1)
        order.refresh_from_db()
        self.assertEqual(order.patient.mrn, "NEW1")

        old.refresh_from_db()
        # Retained, not deleted: the audit trail refers to it.
        self.assertTrue(old.is_merged)
        self.assertEqual(old.merged_into.mrn, "NEW1")

    def test_merging_a_record_into_itself_is_refused(self):
        inbound.handle(msh("ADT^A28") + "\r" + pid(mrn="SAME"))
        code, detail = inbound.handle(
            msh("ADT^A40", "M2") + "\r" + pid(mrn="SAME") + "\r" + "MRG|SAME"
        )
        self.assertEqual(code, "AE")


class OrderMessageTests(TestCase):
    def setUp(self):
        self.test = make_test(code="GLU", name="Glucose")
        self.other = make_test(code="K", name="Potassium")
        Patient.objects.create(
            mrn="MRN900", first_name="John", last_name="Smith",
            dob=date(1980, 1, 1), gender="M",
        )

    def _orm(self, control="NW", placer="PLC1", codes=("GLU",), extra=""):
        segments = [msh("ORM^O01"), pid(), f"ORC|{control}|{placer}||||||||||"]
        for index, code in enumerate(codes, start=1):
            segments.append(f"OBR|{index}|{placer}||{code}^Test^L|R|||||||||||Dr^Jones")
        if extra:
            segments.append(extra)
        return "\r".join(segments)

    def test_a_new_order_is_accessioned(self):
        code, detail = inbound.handle(self._orm())
        self.assertEqual(code, "AA")
        self.assertEqual(detail["action"], "created")

        order = Order.objects.get(accession_number=detail["accession"])
        self.assertEqual(order.placer_order_number, "PLC1")
        self.assertEqual([t.code for t in order.tests.all()], ["GLU"])

    def test_a_retransmitted_order_does_not_produce_a_second_specimen(self):
        inbound.handle(self._orm())
        code, detail = inbound.handle(self._orm())

        self.assertEqual(code, "AA")
        self.assertEqual(detail["action"], "duplicate")
        self.assertEqual(Order.objects.count(), 1)

    def test_a_cancellation_cancels_the_matching_order(self):
        inbound.handle(self._orm())
        code, detail = inbound.handle(self._orm(control="CA"))

        self.assertEqual(code, "AA")
        self.assertEqual(detail["action"], "cancelled")
        self.assertEqual(Order.objects.get().status, OrderStatus.CANCELLED)

    def test_cancelling_an_unknown_order_is_refused(self):
        code, detail = inbound.handle(self._orm(control="CA", placer="NOPE"))
        self.assertEqual(code, "AE")

    def test_an_order_whose_tests_are_all_unknown_is_refused(self):
        code, detail = inbound.handle(self._orm(codes=("ZZZ",)))
        self.assertEqual(code, "AE")
        self.assertIn("ZZZ", detail["error"])
        self.assertEqual(Order.objects.count(), 0)

    def test_a_partially_matched_order_is_accepted_and_reports_the_rest(self):
        code, detail = inbound.handle(self._orm(codes=("GLU", "ZZZ")))
        self.assertEqual(code, "AA")
        self.assertEqual(detail["unmatched_tests"], ["ZZZ"])

    def test_priority_is_mapped(self):
        message = self._orm().replace("|R|||||||||||Dr^Jones", "|S|||||||||||Dr^Jones")
        _, detail = inbound.handle(message)
        self.assertEqual(
            Order.objects.get(accession_number=detail["accession"]).priority, "STAT"
        )

    def test_a_dg1_segment_attaches_an_icd10_diagnosis(self):
        Icd10Code.objects.create(code="E11.9", description="Type 2 diabetes mellitus")
        _, detail = inbound.handle(self._orm(extra="DG1|1||E11.9^Type 2 diabetes^I10||"))

        order = Order.objects.get(accession_number=detail["accession"])
        diagnosis = order.diagnoses.get()
        self.assertEqual(diagnosis.code_value, "E11.9")
        self.assertEqual(diagnosis.description, "Type 2 diabetes mellitus")
        self.assertTrue(diagnosis.is_primary)

    def test_a_diagnosis_not_in_the_catalogue_is_still_recorded(self):
        """The hospital's coding is the record, even when our table lags it."""
        _, detail = inbound.handle(self._orm(extra="DG1|1||R55^Syncope^I10||"))
        order = Order.objects.get(accession_number=detail["accession"])
        self.assertEqual(order.diagnoses.get().code_value, "R55")

    def test_an_order_message_without_a_pid_is_malformed(self):
        message = "\r".join([msh("ORM^O01"), "ORC|NW|PLC1", "OBR|1|PLC1||GLU^Test^L"])
        code, _ = inbound.handle(message)
        self.assertEqual(code, "AR")

    def test_an_unsupported_message_type_is_rejected(self):
        code, detail = inbound.handle(msh("SIU^S12") + "\r" + pid())
        self.assertEqual(code, "AR")
        self.assertIn("not supported", detail["error"])


class AckTests(TestCase):
    def test_the_ack_echoes_the_control_id(self):
        ack = inbound.build_ack(msh("ADT^A28", "CTRL9"), "AA", {"action": "created"})
        self.assertIn("MSA|AA|CTRL9", ack)

    def test_an_error_ack_carries_the_reason(self):
        ack = inbound.build_ack(msh("ADT^A28", "CTRL9"), "AE", {"error": "no MRN"})
        self.assertIn("MSA|AE|CTRL9|no MRN", ack)


@override_settings(INSTRUMENT_INGEST_TOKEN=TOKEN)
class InboundEndpointTests(TestCase):
    def setUp(self):
        make_test(code="GLU")
        Patient.objects.create(
            mrn="MRN900", first_name="John", last_name="Smith",
            dob=date(1980, 1, 1), gender="M",
        )

    def _post(self, body, token=TOKEN):
        return self.client.post(
            "/api/middleware/hl7/", data=body,
            content_type="application/hl7-v2",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def test_a_bad_token_is_refused(self):
        response = self._post(msh("ADT^A28") + "\r" + pid(), token="wrong")
        self.assertEqual(response.status_code, 401)

    def test_a_good_message_returns_an_accept_ack(self):
        response = self._post(msh("ADT^A28") + "\r" + pid())
        self.assertEqual(response.status_code, 200)
        self.assertIn("MSA|AA", response.content.decode())

    def test_a_refused_message_returns_422_and_raises_an_exception_item(self):
        from apps.operations.models import ExceptionItem

        # A new MRN, so the message is a registration rather than an update —
        # the missing date of birth only blocks creating a patient.
        response = self._post(msh("ADT^A28") + "\r" + pid(mrn="MRN901", dob=""))
        self.assertEqual(response.status_code, 422)
        self.assertIn("MSA|AE", response.content.decode())
        self.assertTrue(ExceptionItem.objects.filter(source="inbound_message").exists())

    def test_an_unparsable_message_returns_400(self):
        response = self._post("total nonsense")
        self.assertEqual(response.status_code, 400)
        self.assertIn("MSA|AR", response.content.decode())


class HostQueryResolutionTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.glucose = make_test(code="GLU")
        self.potassium = make_test(code="K", name="Potassium")
        self.order = make_order(
            self.patient, [self.glucose, self.potassium], accession="2026-01-01-0001"
        )

    def test_an_accession_number_resolves(self):
        self.assertEqual(resolve_order("2026-01-01-0001"), self.order)

    def test_a_container_barcode_resolves(self):
        Specimen.objects.create(order=self.order, type="Serum", container_id="TUBE-7")
        self.assertEqual(resolve_order("TUBE-7"), self.order)

    def test_an_unknown_identifier_resolves_to_nothing(self):
        self.assertIsNone(resolve_order("NOPE"))

    def test_only_tests_without_results_are_returned(self):
        Result.objects.create(
            order=self.order, test=self.glucose, test_key=self.glucose.id, value="5.0",
        )
        self.assertEqual(outstanding_tests(self.order), ["K"])

    def test_the_answer_uses_the_analysers_own_codes(self):
        interface = InstrumentInterface.objects.create(
            name="ARCH-1", test_code_map={"GLUC": "GLU", "POT": "K"},
        )
        codes = sorted(outstanding_tests(self.order, interface=interface))
        self.assertEqual(codes, ["GLUC", "POT"])


@override_settings(INSTRUMENT_INGEST_TOKEN=TOKEN)
class HostQueryEndpointTests(TestCase):
    def setUp(self):
        self.patient = make_patient()
        self.test = make_test(code="GLU")
        self.order = make_order(self.patient, [self.test], accession="2026-01-01-0001")
        self.interface = InstrumentInterface.objects.create(
            name="ARCH-1",
            direction=InstrumentInterface.Direction.BIDIRECTIONAL,
        )

    def _query(self, specimen_id, interface=None, token=TOKEN):
        return self.client.post(
            "/api/middleware/query/",
            data=json.dumps({
                "specimen_id": specimen_id,
                "interface_id": (interface or self.interface).pk,
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def test_a_bad_token_is_refused(self):
        self.assertEqual(self._query("2026-01-01-0001", token="wrong").status_code, 401)

    def test_a_known_specimen_returns_its_outstanding_tests(self):
        response = self._query("2026-01-01-0001")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tests"], ["GLU"])
        self.assertEqual(body["status"], HostQuery.Status.ANSWERED)

    def test_being_asked_about_a_specimen_marks_the_order_in_progress(self):
        self._query("2026-01-01-0001")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.IN_PROGRESS)

    def test_an_unknown_specimen_is_answered_not_errored(self):
        body = self._query("NOPE").json()
        self.assertEqual(body["status"], HostQuery.Status.NOT_FOUND)
        self.assertEqual(body["tests"], [])

    def test_a_completed_order_returns_no_work(self):
        self.order.status = OrderStatus.COMPLETED
        self.order.save(update_fields=["status"])
        body = self._query("2026-01-01-0001").json()
        self.assertEqual(body["status"], HostQuery.Status.NO_WORK)

    def test_a_unidirectional_interface_is_refused(self):
        unidirectional = InstrumentInterface.objects.create(
            name="OLD-1", direction=InstrumentInterface.Direction.UNIDIRECTIONAL
        )
        response = self._query("2026-01-01-0001", interface=unidirectional)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            HostQuery.objects.get(interface=unidirectional).status,
            HostQuery.Status.REFUSED,
        )

    def test_every_query_is_recorded(self):
        self._query("2026-01-01-0001")
        query = HostQuery.objects.get()
        self.assertEqual(query.specimen_identifier, "2026-01-01-0001")
        self.assertIsNotNone(query.response_ms)

    def test_the_interface_is_marked_as_having_spoken(self):
        self._query("2026-01-01-0001")
        self.interface.refresh_from_db()
        self.assertIsNotNone(self.interface.last_message_at)
