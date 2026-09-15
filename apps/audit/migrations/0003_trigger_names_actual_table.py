"""Make the append-only trigger name the table that actually fired.

The message was hardcoded to 'audit_events', so a deletion blocked on
electronic_signatures reported the wrong table — which would send an
investigation looking in the wrong place.
"""
from django.db import migrations

from apps.audit import sql


class Migration(migrations.Migration):

    dependencies = [("audit", "0002_immutability")]

    operations = [
        migrations.RunSQL(sql=sql.FORBID_FUNCTION, reverse_sql=migrations.RunSQL.noop),
    ]
