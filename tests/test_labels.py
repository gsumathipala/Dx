"""Code 128 encoding and specimen labels.

The round-trip tests exist because an encoder nobody can check is an encoder
that silently prints labels no scanner reads — and you find that out at the
bench, on a tube, at three in the morning.
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from apps.laboratory import barcodes
from apps.laboratory.labels import Label, html, zpl, zpl_batch
from apps.laboratory.models import Specimen
from tests.factories import make_order, make_patient, make_test, make_user

PASSWORD = "Str0ng-Pass!23"


class Code128Tests(TestCase):
    CASES = [
        "2026-09-16-0007", "TUBE-7", "ABC123", "12345678", "0001", "A",
        "99", "00", "9999", "2026-09-16-0007-ALIQUOT-2", "X1Y2Z3", "MRN001",
        "a-b_c.1", "2026-12-31-9999", "1", "12", "123",
    ]

    def test_every_case_round_trips(self):
        for text in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(
                    barcodes.decode_modules(barcodes.modules(text)), text
                )

    def test_subset_c_is_used_for_digit_runs(self):
        """Eight digits must not cost the same as eight letters on a 25mm label."""
        self.assertLess(
            len(barcodes.modules("12345678")), len(barcodes.modules("ABCDEFGH"))
        )

    def test_the_checksum_is_verified_on_decode(self):
        bits = barcodes.modules("2026-09-16-0007")
        # Corrupt one symbol into a different valid pattern.
        corrupted = barcodes.PATTERNS[7] + bits[11:]
        with self.assertRaises(ValueError):
            barcodes.decode_modules(corrupted)

    def test_non_ascii_is_refused_rather_than_mangled(self):
        with self.assertRaises(ValueError):
            barcodes.modules("Müller")

    def test_the_svg_fetches_nothing(self):
        """It has to render on a machine with no network — a ward printer."""
        svg = barcodes.svg("2026-09-16-0007")
        self.assertTrue(svg.startswith("<svg"))
        for forbidden in ("<script", "<image", "href=", "url("):
            self.assertNotIn(forbidden, svg)
        self.assertIn("2026-09-16-0007", svg)  # human-readable line
        self.assertIn('aria-label="Barcode: 2026-09-16-0007"', svg)

    def test_the_svg_can_omit_the_text_line(self):
        self.assertNotIn("<text", barcodes.svg("ABC", show_text=False))


class LabelContentTests(TestCase):
    def setUp(self):
        self.label = Label(
            accession_number="2026-09-16-0007",
            patient_name="Jane Doe", mrn="MRN001", date_of_birth="17/05/1980",
            specimen_type="Serum", container="TUBE-7", collected_at="16/09 09:12",
            priority="STAT",
        )

    def test_zpl_carries_two_patient_identifiers_and_the_accession(self):
        """NPSG 01.01.01 wants two identifiers; the accession is not one."""
        payload = zpl(self.label)
        self.assertIn("Jane Doe", payload)
        self.assertIn("MRN001", payload)
        self.assertIn("17/05/1980", payload)
        self.assertIn("2026-09-16-0007", payload)

    def test_zpl_is_well_formed(self):
        payload = zpl(self.label)
        self.assertTrue(payload.startswith("^XA"))
        self.assertTrue(payload.rstrip().endswith("^XZ"))
        self.assertIn("^BCN", payload)  # Code 128

    def test_urgency_is_marked(self):
        self.assertIn("STAT", zpl(self.label))

    def test_zpl_control_characters_in_a_name_are_neutralised(self):
        """A patient called ^Smith must not emit a field command."""
        dangerous = Label(
            accession_number="A1", patient_name="^Smith~Jones\\X", mrn="M1",
            date_of_birth="", specimen_type="", container="", collected_at="",
        )
        payload = zpl(dangerous)
        self.assertNotIn("^Smith", payload)
        self.assertNotIn("~Jones", payload)

    def test_a_batch_renders_one_label_per_entry(self):
        payload = zpl_batch([self.label, self.label])
        self.assertEqual(payload.count("^XA"), 2)

    def test_the_html_sheet_is_self_contained(self):
        page = html([self.label])
        self.assertIn("<svg", page)
        for forbidden in ("<link", "<img", "@import"):
            self.assertNotIn(forbidden, page)

    def test_the_html_sheet_escapes_patient_names(self):
        dangerous = Label(
            accession_number="A1", patient_name="<script>alert(1)</script>",
            mrn="M1", date_of_birth="", specimen_type="", container="",
            collected_at="",
        )
        page = html([dangerous])
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)

    def test_copy_markers_appear_only_when_there_are_several(self):
        single = Label(**{**self.label.__dict__, "copies_total": 1})
        several = Label(**{**self.label.__dict__, "copy_number": 2, "copies_total": 3})
        self.assertEqual(single.copy_marker, "")
        self.assertEqual(several.copy_marker, "2/3")


class LabelViewTests(TestCase):
    def setUp(self):
        self.user = make_user("clerk1", role="clerk", password=PASSWORD)
        self.patient = make_patient()
        self.test = make_test()
        self.order = make_order(self.patient, [self.test], accession="2026-09-16-0007")
        Specimen.objects.create(
            order=self.order, type="Serum", container_id="TUBE-7"
        )
        self.client.force_login(self.user)
        self.url = reverse("laboratory:print_labels", args=[self.order.pk])

    def test_the_printable_sheet_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("2026-09-16-0007", body)
        self.assertIn("Jane Doe", body)
        self.assertIn("<svg", body)

    def test_zpl_is_offered_as_a_download(self):
        response = self.client.get(self.url, {"format": "zpl"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("^XA", response.content.decode())
        self.assertIn("attachment", response["Content-Disposition"])

    def test_copies_are_capped(self):
        response = self.client.get(self.url, {"copies": "500"})
        self.assertLessEqual(response.content.decode().count("<svg"), 10)

    def test_an_order_with_no_specimen_row_still_gets_a_label(self):
        Specimen.objects.all().delete()
        response = self.client.get(self.url)
        self.assertIn("2026-09-16-0007", response.content.decode())

    def test_printing_is_recorded(self):
        from apps.audit.models import AuditEvent

        self.client.get(self.url)
        event = AuditEvent.objects.for_entity("laboratory.Order", self.order.pk).first()
        self.assertIn("label(s) printed", event.entity_label)

    def test_clinical_roles_can_print(self):
        """Anyone who accessions or collects needs a label, including a medic."""
        from apps.common.constants import Role

        for role in (Role.MEDIC, Role.SCIENTIST, Role.PHLEBOTOMIST):
            with self.subTest(role=role):
                user = make_user(f"u-{role}", role=role, password=PASSWORD)
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_the_installer_is_refused(self):
        """A label is two patient identifiers and a specimen id on one page."""
        from apps.common.constants import Role

        installer = make_user("inst", role=Role.INSTALLER, password=PASSWORD)
        self.client.force_login(installer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
