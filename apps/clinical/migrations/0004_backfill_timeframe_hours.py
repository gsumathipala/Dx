"""Derive timeframe_hours from the existing text labels.

Without this, conditions created before the field existed would all report a
24-hour window regardless of what their label says — which for a 7-day
notifiable condition would raise false overdue alerts.
"""
from django.db import migrations


def parse(label: str) -> int:
    raw = (label or "24h").strip().lower()
    try:
        value = int(raw.rstrip("hd"))
    except ValueError:
        return 24
    return value * 24 if raw.endswith("d") else value


def backfill(apps, schema_editor):
    NotifiableCondition = apps.get_model("clinical", "NotifiableCondition")
    for condition in NotifiableCondition.objects.all().iterator():
        hours = parse(condition.timeframe)
        if condition.timeframe_hours != hours:
            condition.timeframe_hours = hours
            condition.save(update_fields=["timeframe_hours"])


class Migration(migrations.Migration):

    dependencies = [("clinical", "0003_notifiablecondition_timeframe_hours_and_more")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
