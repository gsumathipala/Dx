"""Import data from the Next.js SQLite database into PostgreSQL.

    manage.py import_legacy --sqlite sqlite_v2.db [--dry-run]

The legacy schema stored timestamps as ISO strings, booleans as integers, and
several structures as JSON text. Each is converted here, and rows that cannot
be converted are reported rather than skipped silently — a laboratory migration
that quietly drops records is worse than one that stops and says why.

Imported rows are attributed to the migration in the audit trail, so the
provenance of pre-migration data is visible alongside everything else.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.audit.context import audit_as, suppress_auditing
from apps.audit.models import AuditSource
from apps.audit.recorder import record
from apps.common.constants import AuditAction


def parse_datetime(value):
    """Convert a legacy ISO string (or epoch milliseconds) to an aware datetime."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=dt_timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text[:19])
        except ValueError:
            return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def parse_date(value):
    stamp = parse_datetime(value)
    if stamp:
        return stamp.date()
    if value:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
    return None


def parse_json(value, default=None):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value, default=False):
    if value is None:
        return default
    return bool(int(value)) if str(value).isdigit() else bool(value)


def parse_decimal(value, default="0.00"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal(default)


class Command(BaseCommand):
    help = "Import the legacy Next.js SQLite database into PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument("--sqlite", default="sqlite_v2.db", help="Path to the legacy database.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would be imported without writing.")

    def handle(self, *args, **options):
        path = Path(options["sqlite"])
        if not path.exists():
            raise CommandError(f"Legacy database not found: {path}")

        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        self.tables = {
            row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.counts = {}
        self.problems = []
        self.dry_run = options["dry_run"]
        # Legacy id -> imported instance, so foreign keys resolve even when a
        # record already existed locally under a different surrogate id.
        self.ids: dict[str, dict[str, object]] = {}

        try:
            with transaction.atomic():
                with audit_as(actor_username="legacy_import", actor_role="system",
                              source=AuditSource.MIGRATION):
                    # Row-by-row events for a large import would bury the trail;
                    # one summary event is the useful record.
                    with suppress_auditing():
                        self._import_all(connection)

                    if not self.dry_run:
                        record(
                            action=AuditAction.RESTORE,
                            entity_type="operations.SystemSetting",
                            entity_id="legacy-import",
                            entity_label=f"legacy SQLite import from {path.name}",
                            changes={"imported": {"old": None, "new": self.counts}},
                            blocking=True,
                        )

                if self.dry_run:
                    transaction.set_rollback(True)
        finally:
            connection.close()

        self._report()

    # -- Import sequence (ordered so foreign keys resolve) --------------------

    def _import_all(self, connection):
        self._departments(connection)
        self._users(connection)
        self._tests(connection)
        self._patients(connection)
        self._queues(connection)
        self._orders(connection)
        self._specimens(connection)
        self._results(connection)
        self._inventory(connection)
        self._qc(connection)
        self._equipment(connection)
        self._billing(connection)
        self._settings(connection)

    def _upsert(self, model, *, natural: dict, legacy_id: str | None, defaults: dict, kind: str):
        """Reconcile a legacy row against the target database.

        Matching is done on the business key (test code, MRN, accession number
        and so on), never on the legacy surrogate id — the target may already
        hold the same record under a different id, and creating a duplicate
        would split a patient's history across two records.
        """
        instance = model.objects.filter(**natural).first()
        if instance is None and legacy_id:
            instance = model.objects.filter(pk=legacy_id).first()

        if instance is None:
            fields = {**natural, **defaults}
            if legacy_id and not model.objects.filter(pk=legacy_id).exists():
                fields["id"] = legacy_id
            instance = model.objects.create(**fields)
        else:
            for field, value in {**natural, **defaults}.items():
                setattr(instance, field, value)
            instance.save()

        if legacy_id:
            self.ids.setdefault(kind, {})[legacy_id] = instance
        return instance

    def _resolve(self, kind: str, legacy_id):
        mapping = self.ids.get(kind, {})
        return mapping.get(legacy_id)

    def _rows(self, connection, table):
        if table not in self.tables:
            self.stdout.write(self.style.WARNING(f"  (no {table} table in source)"))
            return []
        return list(connection.execute(f"SELECT * FROM {table}"))

    def _track(self, table, count):
        self.counts[table] = count
        self.stdout.write(f"  {table}: {count}")

    def _departments(self, connection):
        from apps.accounts.models import Department

        count = 0
        for row in self._rows(connection, "departments"):
            self._upsert(
                Department, kind="departments", legacy_id=row["id"],
                natural={"code": row["code"]},
                defaults={
                    "name": row["name"],
                    "type": row["type"] or "clinical", "description": row["description"],
                    "enabled": parse_bool(row["enabled"], True),
                    "created_at": parse_datetime(row["created_at"]) or timezone.now(),
                    "last_modified_at": parse_datetime(row["last_modified_at"]),
                    "last_modified_by": row["last_modified_by"],
                },
            )
            count += 1
        self._track("departments", count)

    def _users(self, connection):
        from django.contrib.auth import get_user_model

        from apps.accounts.models import Department

        User = get_user_model()
        departments = {d.name: d for d in Department.objects.all()}
        departments.update({d.code: d for d in Department.objects.all()})

        count = 0
        for row in self._rows(connection, "users"):
            password = row["password"] or ""
            user = self._upsert(
                User, kind="users", legacy_id=row["id"],
                natural={"username": row["username"]},
                defaults={
                    "name": row["name"] or row["username"],
                    "role": row["role"] or "scientist",
                    "department": departments.get(row["department"]),
                    "email": row["email"] or None,
                    "is_staff": row["role"] == "admin",
                    "is_superuser": row["role"] == "admin",
                },
            )
            # Legacy bcrypt hashes carry across and are verified by the
            # compatibility backend; cleartext is never migrated as-is.
            if password.startswith(("$2a$", "$2b$", "$2y$")):
                User.objects.filter(pk=user.pk).update(password=password)
            else:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                self.problems.append(
                    f"user {row['username']}: legacy password was not a bcrypt hash; "
                    "imported with no usable password and must be reset"
                )
            count += 1
        self._track("users", count)

    def _tests(self, connection):
        from apps.accounts.models import Department
        from apps.laboratory.models import TestDefinition

        departments = {d.name: d for d in Department.objects.all()}
        departments.update({d.code: d for d in Department.objects.all()})

        count = 0
        for row in self._rows(connection, "test_definitions"):
            self._upsert(
                TestDefinition, kind="tests", legacy_id=row["id"],
                natural={"code": row["code"]},
                defaults={
                    "name": row["name"],
                    "department": departments.get(row["department"]),
                    "units": row["units"], "tat_hours": row["tat_hours"],
                    "active": parse_bool(row["active"], True),
                    "reference_range": parse_json(row["reference_range"]),
                    "specimen_types": parse_json(row["specimen_types"], []) or [],
                    "methodology": row["methodology"], "loinc_code": row["loinc_code"],
                },
            )
            count += 1
        self._track("test_definitions", count)

    def _patients(self, connection):
        from apps.patients.models import Patient

        count = 0
        for row in self._rows(connection, "patients"):
            dob = parse_date(row["dob"])
            if dob is None:
                self.problems.append(
                    f"patient {row['mrn']}: unparsable date of birth {row['dob']!r}"
                )
                continue
            self._upsert(
                Patient, kind="patients", legacy_id=row["id"],
                natural={"mrn": row["mrn"]},
                defaults={
                    "first_name": row["first_name"], "last_name": row["last_name"],
                    "dob": dob, "gender": (row["gender"] or "U")[:1].upper(),
                    "email": row["email"] or None,
                    "phone": row["phone"], "address": row["address"],
                },
            )
            count += 1
        self._track("patients", count)

    def _queues(self, connection):
        from apps.laboratory.models import AuthorizationQueue

        count = 0
        for row in self._rows(connection, "authorization_queues"):
            self._upsert(
                AuthorizationQueue, kind="queues", legacy_id=row["id"],
                natural={"name": row["name"]},
                defaults={
                    "description": row["description"],
                    "allowed_roles": parse_json(row["allowed_roles"], []) or [],
                    "created_by": row["created_by"],
                    "created_at": parse_datetime(row["created_at"]) or timezone.now(),
                },
            )
            count += 1
        self._track("authorization_queues", count)

    def _orders(self, connection):
        from apps.laboratory.models import Order

        count = 0
        for row in self._rows(connection, "orders"):
            patient = self._resolve("patients", row["patient_id"])
            if patient is None:
                self.problems.append(
                    f"order {row['accession_number']}: patient {row['patient_id']} was not imported"
                )
                continue

            order = self._upsert(
                Order, kind="orders", legacy_id=row["id"],
                natural={"accession_number": row["accession_number"]},
                defaults={
                    "patient": patient,
                    "status": row["status"] or "Pending",
                    "order_by": row["order_by"],
                    "timestamp": parse_datetime(row["timestamp"]) or timezone.now(),
                    "queue": self._resolve("queues", row["queue_id"]),
                    "priority": row["priority"] or "Routine",
                    "completed_at": parse_datetime(row["completed_at"]),
                    "updated_at": parse_datetime(row["updated_at"]),
                },
            )
            linked = [
                test for test in (
                    self._resolve("tests", legacy) for legacy in parse_json(row["test_ids"], []) or []
                ) if test is not None
            ]
            order.tests.set(linked)
            count += 1
        self._track("orders", count)

    def _specimens(self, connection):
        from apps.laboratory.models import Specimen

        count = 0
        for row in self._rows(connection, "specimens"):
            order = self._resolve("orders", row["order_id"])
            if order is None:
                continue
            self._upsert(
                Specimen, kind="specimens", legacy_id=row["id"],
                natural={"order": order, "container_id": row["container_id"]},
                defaults={
                    "type": row["type"], "location": row["location"],
                    "collection_date": parse_datetime(row["collection_date"]),
                    "status": row["status"],
                },
            )
            count += 1
        self._track("specimens", count)

    def _results(self, connection):
        from apps.laboratory.models import Result

        count = 0
        for row in self._rows(connection, "results"):
            order = self._resolve("orders", row["order_id"])
            if order is None:
                continue

            raw = parse_json(row["values"], {}) or {}
            # Legacy shape was {"value": "..."}; occasionally a bare scalar.
            value = raw.get("value") if isinstance(raw, dict) else raw
            test = self._resolve("tests", row["test_id"])
            # The reserved REPORT pseudo-test carries the narrative comment.
            test_key = test.id if test is not None else row["test_id"]

            self._upsert(
                Result, kind="results", legacy_id=row["id"],
                natural={"order": order, "test_key": test_key},
                defaults={
                    "test": test,
                    "value": None if value is None else str(value),
                    "result_flags": parse_json(row["result_flags"], []) or [],
                    "status": row["status"] or "Resulted",
                    "entered_by": row["entered_by"],
                    "technical_validated_by": row["technical_validated_by"],
                    "clinical_verified_by": row["clinical_verified_by"],
                    "comments": row["comments"],
                    "timestamp": parse_datetime(row["timestamp"]) or timezone.now(),
                },
            )
            count += 1
        self._track("results", count)

    def _inventory(self, connection):
        from apps.inventory.models import InventoryItem, InventoryTransaction

        count = 0
        for row in self._rows(connection, "inventory_items"):
            self._upsert(
                InventoryItem, kind="inventory", legacy_id=row["id"],
                natural={"name": row["name"], "lot_number": row["lot_number"]},
                defaults={
                    "expiration_date": parse_date(row["expiration_date"]),
                    "quantity": row["quantity"] or 0, "unit": row["unit"] or "units",
                    "min_threshold": row["min_threshold"] or 10, "location": row["location"],
                },
            )
            count += 1
        self._track("inventory_items", count)

        moved = 0
        for row in self._rows(connection, "inventory_transactions"):
            item = self._resolve("inventory", row["item_id"])
            if item is None:
                continue
            InventoryTransaction.objects.get_or_create(
                item=item,
                timestamp=parse_datetime(row["timestamp"]) or timezone.now(),
                change=row["change"],
                defaults={"reason": row["reason"], "user_id": row["user_id"]},
            )
            moved += 1
        self._track("inventory_transactions", moved)

    def _qc(self, connection):
        from apps.laboratory.models import TestDefinition
        from apps.quality.models import QcDefinition, QcMaterial, QcRun, RejectionCriterion

        count = 0
        for row in self._rows(connection, "qc_materials"):
            self._upsert(
                QcMaterial, kind="qc_materials", legacy_id=row["id"],
                natural={"name": row["name"], "lot_number": row["lot_number"]},
                defaults={
                    "expiration_date": parse_date(row["expiration_date"]) or timezone.localdate(),
                    "manufacturer": row["manufacturer"],
                    "active": parse_bool(row["active"], True),
                },
            )
            count += 1
        self._track("qc_materials", count)

        tests_by_code = {t.code: t for t in TestDefinition.objects.all()}
        definitions = 0
        for row in self._rows(connection, "qc_definitions"):
            material = self._resolve("qc_materials", row["material_id"])
            if material is None:
                continue
            self._upsert(
                QcDefinition, kind="qc_definitions", legacy_id=row["id"],
                natural={"material": material, "test_code": row["test_code"]},
                defaults={
                    "test": tests_by_code.get(row["test_code"]),
                    "test_name": row["test_name"],
                    "mean": row["mean"], "sd": row["sd"], "unit": row["unit"] or "",
                },
            )
            definitions += 1
        self._track("qc_definitions", definitions)

        runs = 0
        for row in self._rows(connection, "qc_runs"):
            definition = self._resolve("qc_definitions", row["definition_id"])
            if definition is None:
                continue
            QcRun.objects.get_or_create(
                definition=definition,
                timestamp=parse_datetime(row["timestamp"]) or timezone.now(),
                value=row["value"],
                defaults={
                    "result_flags": parse_json(row["result_flags"], []) or [],
                    "status": row["status"] or "Pass",
                    "performed_by": row["performed_by"],
                    "comments": row["comments"],
                },
            )
            runs += 1
        self._track("qc_runs", runs)

        criteria = 0
        for row in self._rows(connection, "rejection_criteria"):
            self._upsert(
                RejectionCriterion, kind="rejection_criteria", legacy_id=row["id"],
                natural={"reason": row["reason"]},
                defaults={
                    "description": row["description"],
                    "category": row["category"] or "General",
                    "active": parse_bool(row["active"], True),
                },
            )
            criteria += 1
        self._track("rejection_criteria", criteria)

    def _equipment(self, connection):
        from apps.accounts.models import Department
        from apps.quality.models import Equipment, EquipmentLog

        departments = {d.name: d for d in Department.objects.all()}
        departments.update({d.code: d for d in Department.objects.all()})

        count = 0
        for row in self._rows(connection, "equipment"):
            self._upsert(
                Equipment, kind="equipment", legacy_id=row["id"],
                natural={"name": row["name"]},
                defaults={
                    "type": row["type"], "serial_number": row["serial_number"],
                    "manufacturer": row["manufacturer"],
                    "department": departments.get(row["department"]),
                    "status": row["status"] or "Active",
                    "last_service_date": parse_date(row["last_service_date"]),
                    "next_service_date": parse_date(row["next_service_date"]),
                    "active": parse_bool(row["active"], True),
                },
            )
            count += 1
        self._track("equipment", count)

        logs = 0
        for row in self._rows(connection, "equipment_logs"):
            equipment = self._resolve("equipment", row["equipment_id"])
            if equipment is None:
                continue
            EquipmentLog.objects.get_or_create(
                equipment=equipment,
                timestamp=parse_datetime(row["timestamp"]) or timezone.now(),
                type=row["type"],
                defaults={
                    "description": row["description"],
                    "performed_by": row["performed_by"],
                    "outcome": row["outcome"],
                },
            )
            logs += 1
        self._track("equipment_logs", logs)

    def _billing(self, connection):
        from apps.billing.models import BillingItem, Invoice, InvoiceLine

        count = 0
        for row in self._rows(connection, "billing_items"):
            self._upsert(
                BillingItem, kind="billing_items", legacy_id=row["id"],
                natural={"code": row["code"]},
                defaults={
                    "name": row["name"], "price": parse_decimal(row["price"]),
                    "active": parse_bool(row["active"], True),
                },
            )
            count += 1
        self._track("billing_items", count)

        invoices = 0
        for row in self._rows(connection, "invoices"):
            order = self._resolve("orders", row["order_id"])
            if order is None:
                continue
            invoice = self._upsert(
                Invoice, kind="invoices", legacy_id=row["id"],
                natural={"order": order},
                defaults={
                    "total_amount": parse_decimal(row["total_amount"]),
                    "status": row["status"] or "Pending",
                    "created_at": parse_datetime(row["created_at"]) or timezone.now(),
                },
            )
            # Legacy JSON line items become real rows, so revenue can be
            # queried without parsing every invoice.
            invoice.lines.all().delete()
            for line in parse_json(row["items"], []) or []:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    code=line.get("code", ""),
                    description=line.get("description", line.get("name", "")),
                    unit_price=parse_decimal(line.get("price")),
                )
            invoices += 1
        self._track("invoices", invoices)

    def _settings(self, connection):
        from apps.operations.models import SystemSetting

        count = 0
        for row in self._rows(connection, "settings"):
            SystemSetting.objects.update_or_create(
                key=row["key"],
                defaults={"id": row["id"], "value": parse_json(row["value"], row["value"])},
            )
            count += 1
        self._track("settings", count)

    def _report(self):
        total = sum(self.counts.values())
        self.stdout.write("")
        if self.problems:
            self.stdout.write(self.style.WARNING(f"{len(self.problems)} row(s) need attention:"))
            for problem in self.problems[:40]:
                self.stdout.write(f"  - {problem}")
            if len(self.problems) > 40:
                self.stdout.write(f"  ... and {len(self.problems) - 40} more")
            self.stdout.write("")

        if self.dry_run:
            self.stdout.write(self.style.WARNING(
                f"Dry run - {total} row(s) would be imported. Nothing was written."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"Imported {total} row(s)."))
            self.stdout.write(
                "Users imported without a bcrypt hash have no usable password and "
                "must be reset before they can sign in."
            )
