"""Populate a demonstration dataset.

    manage.py seed_demo [--reset]

Creates a coherent laboratory: users with competency, a test catalogue with
reference and critical limits, QC materials with acceptable runs, patients,
orders at each workflow stage, and the clinical rules that act on them.
Intended for evaluation and for exercising the workflow in development.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.audit.context import audit_as
from apps.audit.models import AuditSource

User = get_user_model()

DEMO_PASSWORD = "Dx-Demo-Pass!2026"

TESTS = [
    # code, name, units, dept, min, max, panic low, panic high, loinc, tat
    ("GLU", "Glucose", "mmol/L", "CHEM", 3.9, 5.8, 2.2, 25.0, "2345-7", 2),
    ("NA", "Sodium", "mmol/L", "CHEM", 135, 145, 120, 160, "2951-2", 2),
    ("K", "Potassium", "mmol/L", "CHEM", 3.5, 5.1, 2.5, 6.5, "2823-3", 2),
    ("CREA", "Creatinine", "µmol/L", "CHEM", 60, 110, None, 500, "2160-0", 4),
    ("CL", "Chloride", "mmol/L", "CHEM", 98, 107, None, None, "2075-0", 2),
    ("HCO3", "Bicarbonate", "mmol/L", "CHEM", 22, 29, 10, 40, "1963-8", 2),
    ("ALB", "Albumin", "g/L", "CHEM", 35, 50, None, None, "1751-7", 4),
    ("TP", "Total protein", "g/L", "CHEM", 60, 80, None, None, "2885-2", 4),
    ("TC", "Total cholesterol", "mmol/L", "CHEM", None, 5.2, None, None, "2093-3", 8),
    ("HDL", "HDL cholesterol", "mmol/L", "CHEM", 1.0, None, None, None, "2085-9", 8),
    ("TG", "Triglycerides", "mmol/L", "CHEM", None, 1.7, None, None, "2571-8", 8),
    ("HB", "Haemoglobin", "g/L", "HAEM", 120, 160, 70, 200, "718-7", 2),
    ("WBC", "White cell count", "10^9/L", "HAEM", 4.0, 11.0, 1.0, 30.0, "6690-2", 2),
    ("PLT", "Platelet count", "10^9/L", "HAEM", 150, 400, 50, 1000, "777-3", 2),
    ("TSH", "Thyroid stimulating hormone", "mIU/L", "CHEM", 0.4, 4.0, None, None, "3016-3", 24),
    ("FT4", "Free thyroxine", "pmol/L", "CHEM", 9.0, 19.0, None, None, "3024-7", 24),
    ("CULT", "Bacterial culture", "", "MICRO", None, None, None, None, "600-7", 72),
]

USERS = [
    ("admin", "System Administrator", "admin", None),
    ("lmanager", "Laboratory Manager", "manager", "CHEM"),
    ("bscientist", "Senior Biomedical Scientist", "scientist", "CHEM"),
    ("jtech", "Junior Technologist", "scientist", "HAEM"),
    ("dmedic", "Duty Medical Officer", "medic", None),
    ("rclerk", "Reception Clerk", "clerk", None),
    ("pphleb", "Phlebotomist", "phlebotomist", None),
]

PATIENTS = [
    ("Amara", "Okafor", date(1978, 3, 14), "F", "MRN-100001"),
    ("Devan", "Ramesh", date(1965, 11, 2), "M", "MRN-100002"),
    ("Sofia", "Lindqvist", date(1992, 7, 21), "F", "MRN-100003"),
    ("Tomas", "Bergmann", date(1954, 1, 9), "M", "MRN-100004"),
    ("Lena", "Petrova", date(2019, 5, 30), "F", "MRN-100005"),
    ("Kwame", "Mensah", date(1988, 9, 17), "M", "MRN-100006"),
]


class Command(BaseCommand):
    help = "Create a demonstration dataset."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing demo records first (never touches the audit trail).")

    @transaction.atomic
    def handle(self, *args, **options):
        with audit_as(actor_username="seed_demo", actor_role="system", source=AuditSource.CLI):
            if options["reset"]:
                self._reset()
            departments = self._departments()
            tests = self._tests(departments)
            users = self._users(departments)
            self._competency(users, tests)
            self._qc(tests, departments)
            self._inventory(tests)
            self._rules(tests)
            self._terminology()
            self._decision_rules(tests, users)
            self._billing(tests)
            patients = self._patients()
            self._orders(patients, tests, users)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data created. Sign in as any of: "
            f"{', '.join(username for username, *_ in USERS)} — password {DEMO_PASSWORD}"
        ))
        self.stdout.write(
            "These accounts share one publicly documented password and exist for "
            "evaluation only. Delete or disable them before this system holds real "
            "patient data. Account roles are listed in INSTALL.md."
        )

    # ── Builders ─────────────────────────────────────────────────────────────

    def _reset(self):
        from apps.clinical.models import (
            CriticalValueNotification, DeltaCheckFlag, DeltaCheckRule,
            EpidemiologyNotification, ReflexActivation, ReflexRule,
        )
        from apps.laboratory.models import Order, Result, Specimen
        from apps.patients.models import Patient

        for model in (Result, DeltaCheckFlag, CriticalValueNotification,
                      ReflexActivation, EpidemiologyNotification, Specimen, Order, Patient):
            model.objects.all().delete()
        self.stdout.write("Existing demo records removed.")

    def _departments(self):
        from apps.accounts.models import Department

        data = [("Clinical Chemistry", "CHEM"), ("Haematology", "HAEM"),
                ("Microbiology", "MICRO"), ("Histopathology", "HISTO")]
        return {
            code: Department.objects.get_or_create(
                code=code, defaults={"name": name, "created_at": timezone.now()}
            )[0]
            for name, code in data
        }

    def _tests(self, departments):
        from apps.laboratory.models import TestDefinition

        tests = {}
        for code, name, units, dept, low, high, panic_low, panic_high, loinc, tat in TESTS:
            reference = {}
            if low is not None:
                reference["min"] = low
            if high is not None:
                reference["max"] = high
            if panic_low is not None:
                reference["panicLow"] = panic_low
            if panic_high is not None:
                reference["panicHigh"] = panic_high

            tests[code] = TestDefinition.objects.get_or_create(
                code=code,
                defaults={
                    "name": name, "units": units, "department": departments.get(dept),
                    "reference_range": reference or None, "loinc_code": loinc,
                    "tat_hours": tat, "specimen_types": ["Serum"] if dept == "CHEM" else ["Whole blood"],
                },
            )[0]
        return tests

    def _users(self, departments):
        users = {}
        for username, name, role, dept in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"name": name, "role": role, "department": departments.get(dept),
                          "is_staff": role == "admin", "is_superuser": role == "admin"},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                from apps.compliance.services import record_password_change

                record_password_change(user)
            users[username] = user
        return users

    def _competency(self, users, tests):
        from apps.accounts.models import UserCompetency

        today = timezone.localdate()
        for username in ("lmanager", "bscientist", "jtech", "dmedic"):
            for test in tests.values():
                UserCompetency.objects.get_or_create(
                    user=users[username], test=test,
                    defaults={
                        "competency_date": today - timedelta(days=60),
                        "expiry_date": today + timedelta(days=305),
                        "assessed_by": "lmanager",
                    },
                )

    def _qc(self, tests, departments):
        from apps.quality.models import (
            Equipment, QcDefinition, QcMaterial, QcRun, RejectionCriterion, evaluate_westgard,
        )

        for reason, category in [
            ("Haemolysed sample", "Quality"), ("Insufficient volume", "Quantity"),
            ("Unlabelled specimen", "Labeling"), ("Clotted sample", "Quality"),
            ("Incorrect container", "Quality"), ("Delayed transport", "Transport"),
        ]:
            RejectionCriterion.objects.get_or_create(reason=reason, defaults={"category": category})

        analyser = Equipment.objects.get_or_create(
            name="Chemistry analyser A1",
            defaults={
                "type": "Clinical chemistry analyser", "manufacturer": "Demo Instruments",
                "serial_number": "CA-2201", "department": departments["CHEM"],
                "last_calibration_date": timezone.localdate() - timedelta(days=20),
                "next_calibration_date": timezone.localdate() + timedelta(days=70),
                "last_service_date": timezone.localdate() - timedelta(days=40),
                "next_service_date": timezone.localdate() + timedelta(days=140),
            },
        )[0]

        material = QcMaterial.objects.get_or_create(
            name="Multichem Level 2", lot_number="LOT-24-118",
            defaults={"expiration_date": timezone.localdate() + timedelta(days=200),
                      "manufacturer": "Demo Controls", "level": "Level 2"},
        )[0]

        targets = {"GLU": (5.4, 0.18), "NA": (140.0, 1.6), "K": (4.2, 0.12),
                   "CREA": (88.0, 3.5), "HB": (135.0, 3.0), "WBC": (7.2, 0.4),
                   "PLT": (250.0, 12.0)}

        for code, (mean, sd) in targets.items():
            definition = QcDefinition.objects.get_or_create(
                material=material, test_code=code,
                defaults={"test": tests[code], "test_name": tests[code].name,
                          "mean": mean, "sd": sd, "unit": tests[code].units or ""},
            )[0]
            # A short run of acceptable QC so the lockout does not block the demo.
            if not definition.runs.exists():
                offsets = [0.0, 0.6, -0.4, 0.9, -0.7, 0.3]
                for index, offset in enumerate(offsets):
                    value = round(mean + offset * sd, 3)
                    when = timezone.now() - timedelta(hours=len(offsets) - index)
                    history = list(
                        QcRun.objects.filter(definition=definition)
                        .order_by("-timestamp").values_list("value", flat=True)[:12]
                    )
                    status, flags = evaluate_westgard(definition, value, history)
                    QcRun.objects.create(
                        definition=definition, value=value, status=status, result_flags=flags,
                        z_score=definition.z_score(value), performed_by="bscientist",
                        timestamp=when, instrument=analyser,
                    )

    def _inventory(self, tests):
        from apps.inventory.models import InventoryItem

        for code, name, quantity in [
            ("GLU", "Glucose reagent pack", 240), ("NA", "Electrolyte cartridge", 180),
            ("K", "Electrolyte cartridge", 180), ("CREA", "Creatinine reagent", 90),
            ("HB", "Haematology lyse reagent", 60), ("CULT", "Blood agar plates", 25),
        ]:
            item = InventoryItem.objects.get_or_create(
                name=name, lot_number=f"R-{code}-01",
                defaults={"quantity": quantity, "unit": "tests", "min_threshold": 40,
                          "location": "Main store",
                          "expiration_date": timezone.localdate() + timedelta(days=180)},
            )[0]
            item.tests.add(tests[code])

    def _rules(self, tests):
        from apps.clinical.models import (
            CalculatedTest, DeltaCheckRule, DemographicReferenceRange,
            NotifiableCondition, ReflexRule,
        )

        DeltaCheckRule.objects.get_or_create(
            test=tests["CREA"],
            defaults={"test_code": "CREA", "delta_type": "percent", "threshold": 50,
                      "direction": "any", "lookback_days": 30, "created_by": "lmanager"},
        )
        DeltaCheckRule.objects.get_or_create(
            test=tests["HB"],
            defaults={"test_code": "HB", "delta_type": "absolute", "threshold": 20,
                      "direction": "decrease", "lookback_days": 14, "created_by": "lmanager"},
        )
        ReflexRule.objects.get_or_create(
            name="Raised TSH reflexes free T4",
            defaults={"trigger_test": tests["TSH"], "operator": ">", "threshold": 4.0,
                      "add_test": tests["FT4"], "add_test_code": "FT4", "created_by": "lmanager"},
        )
        DemographicReferenceRange.objects.get_or_create(
            test=tests["CREA"], age_min=0, age_max=12, gender="All",
            defaults={"test_code": "CREA", "low_normal": 20, "high_normal": 60,
                      "low_critical": None, "high_critical": 200, "unit": "µmol/L",
                      "notes": "Paediatric interval", "created_at": timezone.now()},
        )
        DemographicReferenceRange.objects.get_or_create(
            test=tests["HB"], gender="F", age_min=18, age_max=120,
            defaults={"test_code": "HB", "low_normal": 120, "high_normal": 150,
                      "low_critical": 70, "high_critical": 200, "unit": "g/L",
                      "created_at": timezone.now()},
        )
        for code, name, formula, inputs, unit in [
            ("LDLC", "LDL cholesterol (calculated)", "ldl_friedewald", ["TC", "HDL", "TG"], "mmol/L"),
            ("AGAP", "Anion gap", "anion_gap", ["Na", "Cl", "HCO3"], "mmol/L"),
            ("EGFR", "eGFR (CKD-EPI 2021)", "egfr_ckd_epi", ["CREA"], "mL/min/1.73m²"),
            ("AGR", "Albumin/globulin ratio", "a_g_ratio", ["ALB", "TP"], ""),
        ]:
            CalculatedTest.objects.get_or_create(
                test_code=code,
                defaults={"name": name, "formula": formula, "inputs": inputs,
                          "unit": unit, "created_at": timezone.now()},
            )
        condition = NotifiableCondition.objects.get_or_create(
            name="Salmonellosis",
            defaults={"organism": "Salmonella spp.", "reporting_body": "Public Health Agency",
                      "timeframe": "24h", "created_at": timezone.now()},
        )[0]
        condition.tests.add(tests["CULT"])

    def _terminology(self):
        """A handful of ICD-10 codes, enough to demonstrate coded indications.

        Not a catalogue. A laboratory populates this from whatever
        authoritative source it is entitled to use.
        """
        from apps.interop.models import Icd10Code

        for code, description, chapter in [
            ("E11.9", "Type 2 diabetes mellitus without complications",
             "Endocrine, nutritional and metabolic diseases"),
            ("E87.1", "Hypo-osmolality and hyponatraemia",
             "Endocrine, nutritional and metabolic diseases"),
            ("E87.5", "Hyperkalaemia",
             "Endocrine, nutritional and metabolic diseases"),
            ("N18.3", "Chronic kidney disease, stage 3",
             "Diseases of the genitourinary system"),
            ("D50.9", "Iron deficiency anaemia, unspecified",
             "Diseases of the blood and blood-forming organs"),
            ("E03.9", "Hypothyroidism, unspecified",
             "Endocrine, nutritional and metabolic diseases"),
            ("R55", "Syncope and collapse",
             "Symptoms, signs and abnormal clinical findings"),
            ("A09", "Infectious gastroenteritis and colitis, unspecified",
             "Certain infectious and parasitic diseases"),
        ]:
            Icd10Code.objects.get_or_create(
                code=code,
                defaults={"description": description, "chapter": chapter,
                          "category": code.split(".")[0], "billable": True},
            )

    def _decision_rules(self, tests, users):
        """Three worked examples of the rules engine.

        Two append interpretive comments — which is what most laboratories
        build first — and one demonstrates autoverification on a single analyte
        the "laboratory" has explicitly permitted. All three are approved, so
        they actually fire in the demonstration.
        """
        from apps.rules.models import Rule, RuleAction, RuleCondition

        approver = users.get("lmanager")

        def approve(rule):
            rule.approved_by = approver
            rule.approved_at = timezone.now()
            rule.approved_version = rule.version
            rule.save(update_fields=["approved_by", "approved_at", "approved_version"])

        # ── 1. Haemolysis suppression note on potassium ──────────────────────
        rule, created = Rule.objects.get_or_create(
            name="Haemolysis — potassium suppression note",
            defaults={
                "description": (
                    "Potassium leaks from red cells in vitro. A haemolysed "
                    "specimen gives a number that is real as a measurement and "
                    "wrong as a clinical fact. Warn the requester rather than "
                    "reporting it alone."
                ),
                "trigger": Rule.Trigger.RESULT_ENTERED,
                "test": tests["K"],
                "priority": 50,
            },
        )
        if created:
            RuleCondition.objects.create(
                rule=rule, group=0, subject=RuleCondition.Subject.RESULT_VALUE,
                operator=RuleCondition.Operator.GT, value="5.5",
            )
            RuleCondition.objects.create(
                rule=rule, group=0, subject=RuleCondition.Subject.SPECIMEN_CONDITION,
                operator=RuleCondition.Operator.EQ, value="Marginal", position=1,
            )
            RuleAction.objects.create(
                rule=rule, kind=RuleAction.Kind.APPEND_COMMENT,
                text=(
                    "Potassium may be falsely elevated: specimen recorded as "
                    "haemolysed at reception. Suggest repeat on a fresh sample "
                    "if clinically unexpected."
                ),
            )
            approve(rule)

        # ── 2. Interpretive note on a markedly raised random glucose ─────────
        rule, created = Rule.objects.get_or_create(
            name="Raised random glucose — fasting sample advised",
            defaults={
                "description": (
                    "A single raised random glucose is not a diagnosis. Point "
                    "the requester at the next step rather than at a number."
                ),
                "trigger": Rule.Trigger.RESULT_ENTERED,
                "test": tests["GLU"],
                "priority": 60,
            },
        )
        if created:
            RuleCondition.objects.create(
                rule=rule, group=0, subject=RuleCondition.Subject.RESULT_VALUE,
                operator=RuleCondition.Operator.GTE, value="11.1",
            )
            RuleAction.objects.create(
                rule=rule, kind=RuleAction.Kind.APPEND_COMMENT,
                text=(
                    "Random glucose at or above 11.1 mmol/L. If the patient is "
                    "symptomatic this supports a diagnosis of diabetes; if not, "
                    "a repeat fasting sample or HbA1c is required for "
                    "confirmation."
                ),
            )
            RuleAction.objects.create(
                rule=rule, kind=RuleAction.Kind.SET_FLAG, flag="Review", position=1,
            )
            approve(rule)

        # ── 3. Autoverification, on one analyte, explicitly permitted ────────
        sodium = tests["NA"]
        if not sodium.auto_verify_permitted:
            sodium.auto_verify_permitted = True
            sodium.save(update_fields=["auto_verify_permitted"])

        rule, created = Rule.objects.get_or_create(
            name="Autoverify routine sodium",
            defaults={
                "description": (
                    "Release routine sodium without human review. Every "
                    "guardrail still applies: in-control QC, numeric, within "
                    "the patient's reference interval, no critical value, no "
                    "delta flag, no other flag, acceptable specimen, no open "
                    "exception on the order."
                ),
                "trigger": Rule.Trigger.RESULT_ENTERED,
                "test": sodium,
                "priority": 200,
            },
        )
        if created:
            RuleCondition.objects.create(
                rule=rule, group=0, subject=RuleCondition.Subject.ORDER_PRIORITY,
                operator=RuleCondition.Operator.EQ, value="Routine",
            )
            RuleAction.objects.create(rule=rule, kind=RuleAction.Kind.AUTO_VERIFY)
            approve(rule)

    def _billing(self, tests):
        from apps.billing.models import BillingItem

        prices = {"GLU": "4.50", "NA": "5.00", "K": "5.00", "CREA": "6.20",
                  "HB": "7.10", "WBC": "7.10", "PLT": "7.10", "TSH": "18.40", "CULT": "32.00"}
        for code, price in prices.items():
            item = BillingItem.objects.get_or_create(
                code=f"B-{code}",
                defaults={"name": f"{tests[code].name} assay", "price": Decimal(price)},
            )[0]
            item.tests.add(tests[code])

    def _patients(self):
        from apps.patients.models import Patient

        return [
            Patient.objects.get_or_create(
                mrn=mrn,
                defaults={"first_name": first, "last_name": last, "dob": dob, "gender": gender},
            )[0]
            for first, last, dob, gender, mrn in PATIENTS
        ]

    def _orders(self, patients, tests, users):
        """Create orders spread across the workflow, including a prior episode
        so delta checks have something to compare against."""
        from apps.laboratory.services import create_order, save_results
        from apps.common.constants import AuditAction

        chemistry = [tests["GLU"], tests["NA"], tests["K"], tests["CREA"]]
        haematology = [tests["HB"], tests["WBC"], tests["PLT"]]

        # A historic episode, so the delta check has a predecessor.
        historic = create_order(patient=patients[0], tests=[tests["CREA"]],
                                ordered_by="Dr Historic", user=users["rclerk"])
        historic.timestamp = timezone.now() - timedelta(days=10)
        historic.save(update_fields=["timestamp"])
        save_results(order=historic, values={tests["CREA"].id: "85"}, user=users["bscientist"])

        # A completed, verified order.
        completed = create_order(patient=patients[0], tests=chemistry,
                                 ordered_by="Dr Adeyemi", user=users["rclerk"])
        save_results(order=completed,
                     values={t.id: v for t, v in zip(chemistry, ["5.1", "139", "4.3", "150"])},
                     user=users["jtech"])
        save_results(order=completed,
                     values={t.id: v for t, v in zip(chemistry, ["5.1", "139", "4.3", "150"])},
                     user=users["bscientist"], action=AuditAction.CLINICAL_VERIFY,
                     password=DEMO_PASSWORD, notes="Renal function deteriorating; repeat in one week.")

        # An order resulted but awaiting verification.
        awaiting = create_order(patient=patients[1], tests=haematology,
                                ordered_by="Dr Chowdhury", user=users["rclerk"])
        save_results(order=awaiting,
                     values={t.id: v for t, v in zip(haematology, ["96", "13.4", "142"])},
                     user=users["jtech"])

        # A STAT order with a critical potassium.
        stat = create_order(patient=patients[3], tests=[tests["K"], tests["GLU"]],
                            ordered_by="Dr Emergency", priority="STAT", user=users["rclerk"])
        save_results(order=stat, values={tests["K"].id: "6.9", tests["GLU"].id: "27.5"},
                     user=users["jtech"])

        # A reflex-triggering thyroid request.
        thyroid = create_order(patient=patients[2], tests=[tests["TSH"]],
                               ordered_by="Dr Lindqvist", user=users["rclerk"])
        save_results(order=thyroid, values={tests["TSH"].id: "8.7"}, user=users["bscientist"])

        # A paediatric order, to exercise the demographic reference interval.
        create_order(patient=patients[4], tests=[tests["CREA"], tests["HB"]],
                     ordered_by="Dr Paediatrics", user=users["rclerk"])

        # An open request awaiting results.
        create_order(patient=patients[5], tests=[tests["CULT"]],
                     ordered_by="Dr Mensah", user=users["rclerk"])
