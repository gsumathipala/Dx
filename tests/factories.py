"""Minimal object builders for the test suite."""
from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Department, UserCompetency
from apps.laboratory.models import Order, TestDefinition
from apps.patients.models import Patient
from apps.quality.models import QcDefinition, QcMaterial, QcRun

User = get_user_model()


def make_user(username="tech", role="scientist", password="Str0ng-Pass!23", **extra):
    return User.objects.create_user(
        username=username, password=password, name=username.title(), role=role, **extra
    )


def make_department(name="Chemistry", code="CHEM"):
    return Department.objects.create(name=name, code=code)


def make_test(code="GLU", name="Glucose", units="mmol/L", reference_range=None, department=None):
    return TestDefinition.objects.create(
        code=code,
        name=name,
        units=units,
        department=department,
        reference_range=reference_range if reference_range is not None else {
            "min": 3.9, "max": 5.8, "panicLow": 2.2, "panicHigh": 25.0,
        },
    )


def make_patient(mrn="MRN001", dob=date(1980, 5, 17), gender="F"):
    return Patient.objects.create(
        first_name="Jane", last_name="Doe", dob=dob, gender=gender, mrn=mrn
    )


def make_order(patient, tests=(), *, priority="Routine", when=None, accession=None):
    order = Order.objects.create(
        patient=patient,
        accession_number=accession or f"2026-01-01-{Order.objects.count() + 1:04d}",
        status="Pending",
        priority=priority,
        timestamp=when or timezone.now(),
    )
    if tests:
        order.tests.set(tests)
    return order


def grant_competency(user, test=None, category=None, years=1):
    return UserCompetency.objects.create(
        user=user,
        test=test,
        category=category,
        competency_date=timezone.localdate(),
        expiry_date=timezone.localdate() + timedelta(days=365 * years),
        assessed_by="supervisor",
    )


def passing_qc(test, when=None):
    material = QcMaterial.objects.create(
        name=f"{test.code} control", lot_number="L1",
        expiration_date=timezone.localdate() + timedelta(days=180),
    )
    definition = QcDefinition.objects.create(
        material=material, test=test, test_code=test.code, test_name=test.name,
        mean=5.0, sd=0.2, unit=test.units or "",
    )
    return QcRun.objects.create(
        definition=definition, value=5.0, status=QcRun.Status.PASS,
        performed_by="qc-tech", timestamp=when or timezone.now(),
    )


def failing_qc(test, when=None):
    run = passing_qc(test, when=when)
    run.value = 9.9
    run.status = QcRun.Status.FAIL
    run.result_flags = ["1-3s"]
    run.save()
    return run
