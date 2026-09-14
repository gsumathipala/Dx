"""Enforce audit-trail immutability inside PostgreSQL itself.

Application-level guards stop the ordinary code paths, but an audit trail is
only credible if it also resists a direct `UPDATE`/`DELETE` from a database
session. These triggers make the table genuinely append-only: even the table
owner cannot rewrite history without first dropping the trigger, which is
itself a DDL event a reviewer can detect.

``TRUNCATE`` is blocked separately because it does not fire row-level triggers.
Electronic signatures get the same protection (21 CFR Part 11 §11.70).
"""
from django.db import migrations

from apps.audit import sql


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
        ("compliance", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=sql.FORBID_FUNCTION, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(sql=sql.CREATE_TRIGGERS, reverse_sql=sql.DROP_TRIGGERS),
        migrations.RunSQL(sql=sql.CREATE_SIGNATURE_TRIGGERS, reverse_sql=sql.DROP_SIGNATURE_TRIGGERS),
    ]
