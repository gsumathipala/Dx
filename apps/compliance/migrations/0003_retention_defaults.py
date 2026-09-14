"""Seed the CLIA record-retention schedule.

Periods come from 42 CFR §493.1105 (record retention requirements). They are
seeded as data, not hard-coded, so a laboratory operating under a stricter
local rule can lengthen them without a code change.
"""
from django.db import migrations

DEFAULTS = [
    # (record_class, years, citation)
    ("requisition", 2, "CLIA 42 CFR §493.1105(a)(1)"),
    ("test_record", 2, "CLIA 42 CFR §493.1105(a)(2)"),
    ("qc_record", 2, "CLIA 42 CFR §493.1105(a)(4)"),
    ("pt_record", 2, "CLIA 42 CFR §493.1105(a)(6)"),
    ("instrument", 2, "CLIA 42 CFR §493.1105(a)(5)"),
    ("personnel", 2, "CLIA 42 CFR §493.1105(a)(7) — retain while employed plus 2 years"),
    ("blood_bank", 5, "CLIA 42 CFR §493.1105(a)(3) — immunohaematology"),
    ("pathology", 10, "CLIA 42 CFR §493.1105(a)(2)(ii) — pathology reports"),
    ("cytology_slide", 5, "CLIA 42 CFR §493.1105(a)(7)(i)"),
    ("histology_block", 2, "CLIA 42 CFR §493.1105(a)(7)(ii)"),
    ("audit", 10, "21 CFR Part 11 §11.10(e) — retain for the record retention period"),
]


def seed(apps, schema_editor):
    RetentionSchedule = apps.get_model("compliance", "RetentionSchedule")
    for record_class, years, citation in DEFAULTS:
        RetentionSchedule.objects.update_or_create(
            record_class=record_class,
            defaults={"retention_years": years, "citation": citation, "active": True},
        )


def unseed(apps, schema_editor):
    RetentionSchedule = apps.get_model("compliance", "RetentionSchedule")
    RetentionSchedule.objects.filter(record_class__in=[c for c, _, _ in DEFAULTS]).delete()


class Migration(migrations.Migration):

    dependencies = [("compliance", "0002_initial")]

    operations = [migrations.RunPython(seed, unseed)]
