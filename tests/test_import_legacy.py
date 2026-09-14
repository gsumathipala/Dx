"""Legacy SQLite import: type conversion, reconciliation and credential safety."""
from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

import bcrypt
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.laboratory.models import Order, Result
from apps.patients.models import Patient
from tests.factories import make_user

User = get_user_model()

ISO = lambda d: d.isoformat().replace("+00:00", "Z")  # noqa: E731


def build_legacy_db(path: Path, *, admin_password: str = "legacy-pass") -> dict:
    """Create a SQLite database in the legacy shape and populate it."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE departments (id text PRIMARY KEY, name text, code text, type text,
            description text, enabled integer, created_at text, last_modified_at text,
            last_modified_by text);
        CREATE TABLE users (id text PRIMARY KEY, username text, password text, role text,
            name text, department text, email text);
        CREATE TABLE test_definitions (id text PRIMARY KEY, code text, name text,
            department text, units text, tat_hours real, active integer,
            reference_range text, specimen_types text, methodology text, loinc_code text);
        CREATE TABLE patients (id text PRIMARY KEY, first_name text, last_name text,
            dob text, gender text, mrn text, email text, phone text, address text);
        CREATE TABLE orders (id text PRIMARY KEY, patient_id text, accession_number text,
            status text, order_by text, timestamp text, queue_id text, priority text,
            completed_at text, updated_at text, test_ids text);
        CREATE TABLE results (id text PRIMARY KEY, order_id text, test_id text,
            "values" text, result_flags text, status text, entered_by text,
            technical_validated_by text, clinical_verified_by text, comments text,
            timestamp text);
        """
    )

    now = datetime.now(dt_timezone.utc)
    ids = {"dept": str(uuid.uuid4()), "glu": str(uuid.uuid4()),
           "patient": str(uuid.uuid4()), "bad_patient": str(uuid.uuid4()),
           "order": str(uuid.uuid4())}

    conn.execute("INSERT INTO departments VALUES (?,?,?,?,?,?,?,?,?)",
                 (ids["dept"], "Clinical Chemistry", "CHEM", "clinical", None, 1, ISO(now), None, None))

    hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt(rounds=4)).decode()
    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                 ("legacy-admin", "admin", hashed, "admin", "Legacy Admin", "Clinical Chemistry", None))
    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                 (str(uuid.uuid4()), "oldtech", "plaintext123", "scientist", "Old Tech", None, None))

    conn.execute("INSERT INTO test_definitions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (ids["glu"], "GLU", "Glucose", "Clinical Chemistry", "mmol/L", 2, 1,
                  json.dumps({"min": 3.9, "max": 5.8}), json.dumps(["Serum"]), "Hexokinase", "2345-7"))

    conn.execute("INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?)",
                 (ids["patient"], "Ada", "Lovelace", "1985-12-10", "F", "MRN-L-001", None, None, None))
    conn.execute("INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?)",
                 (ids["bad_patient"], "Bad", "Record", "not-a-date", "M", "MRN-L-002", None, None, None))

    conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (ids["order"], ids["patient"], "2025-12-01-0001", "Completed", "Dr Legacy",
                  ISO(now - timedelta(days=3)), None, "Routine",
                  ISO(now - timedelta(days=2)), ISO(now - timedelta(days=2)),
                  json.dumps([ids["glu"]])))
    conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (str(uuid.uuid4()), ids["bad_patient"], "2025-12-01-0002", "Pending",
                  "Dr Legacy", ISO(now), None, "Routine", None, None, json.dumps([])))

    conn.execute('INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                 (str(uuid.uuid4()), ids["order"], ids["glu"], json.dumps({"value": "5.2"}),
                  json.dumps([]), "Clinically Verified", "oldtech", "admin", "admin", None,
                  ISO(now - timedelta(days=3))))
    conn.execute('INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                 (str(uuid.uuid4()), ids["order"], "REPORT", None, None, "Clinically Verified",
                  None, None, None, "Mild hyponatraemia noted.", ISO(now - timedelta(days=3))))

    conn.commit()
    conn.close()
    return ids


class LegacyImportTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "legacy.db"
        self.ids = build_legacy_db(self.db)

    def _import(self, **kwargs):
        call_command("import_legacy", sqlite=str(self.db), verbosity=0, **kwargs)

    def test_records_are_imported_with_converted_types(self):
        self._import()
        patient = Patient.objects.get(mrn="MRN-L-001")
        self.assertEqual(patient.dob.isoformat(), "1985-12-10")

        order = Order.objects.get(accession_number="2025-12-01-0001")
        self.assertEqual([t.code for t in order.tests.all()], ["GLU"])
        self.assertIsNotNone(order.completed_at)

        result = Result.objects.get(order=order, test__code="GLU")
        self.assertEqual(result.value, "5.2")
        self.assertEqual(result.numeric_value, 5.2)

        narrative = Result.objects.get(order=order, test_key="REPORT")
        self.assertEqual(narrative.comments, "Mild hyponatraemia noted.")

    def test_dry_run_writes_nothing(self):
        self._import(dry_run=True)
        self.assertFalse(Patient.objects.filter(mrn="MRN-L-001").exists())
        self.assertFalse(Order.objects.exists())

    def test_unconvertible_rows_are_skipped_not_half_written(self):
        self._import()
        self.assertFalse(Patient.objects.filter(mrn="MRN-L-002").exists())
        self.assertFalse(Order.objects.filter(accession_number="2025-12-01-0002").exists())

    def test_legacy_bcrypt_password_still_authenticates(self):
        self._import()
        self.assertIsNotNone(authenticate(username="admin", password="legacy-pass"))

    def test_cleartext_password_is_imported_unusable(self):
        self._import()
        self.assertFalse(User.objects.get(username="oldtech").has_usable_password())

    def test_existing_account_keeps_its_own_password(self):
        """A migration must never replace a live account's credentials.

        Regression: importing into a populated database overwrote the existing
        administrator's password with the one from the legacy export.
        """
        existing = make_user("admin", role="admin", password="Local-Str0ng!23")
        self._import()

        existing.refresh_from_db()
        self.assertIsNotNone(authenticate(username="admin", password="Local-Str0ng!23"))
        self.assertIsNone(authenticate(username="admin", password="legacy-pass"))

    def test_importing_twice_does_not_duplicate_records(self):
        self._import()
        self._import()
        self.assertEqual(Patient.objects.filter(mrn="MRN-L-001").count(), 1)
        self.assertEqual(Order.objects.filter(accession_number="2025-12-01-0001").count(), 1)
        self.assertEqual(User.objects.filter(username="admin").count(), 1)

    def test_records_matching_on_business_key_are_not_duplicated(self):
        """A patient already present under a different id must be reused."""
        Patient.objects.create(
            first_name="Ada", last_name="Lovelace", dob="1985-12-10",
            gender="F", mrn="MRN-L-001",
        )
        self._import()
        self.assertEqual(Patient.objects.filter(mrn="MRN-L-001").count(), 1)

    def test_import_is_recorded_in_the_audit_trail(self):
        from apps.audit.models import AuditEvent
        from apps.audit.recorder import recorder

        self._import()
        recorder.flush(timeout=5)
        self.assertTrue(
            AuditEvent.objects.filter(actor_username="legacy_import", source="migration").exists()
        )
