---
title: Backup, restore and maintenance
summary: Protecting the data, the audit-trigger step restoring requires, and what to verify afterwards.
audience: administrator
keywords: backup, restore, pg_dump, maintenance, encryption, disaster recovery
---

## Maintenance

**Maintenance** shows audit health — whether the recorder is running, whether
the append-only protection is installed, when the chain was last verified,
whether anything is waiting in the spool — and the commands for backup and
verification.

Operational commands live on the command line deliberately. They then appear in
shell history, can be supervised and scheduled, and are captured by
configuration management.

## Backing up

```bash
pg_dump --format=custom dx > dx-$(date +%F).dump
```

### Encrypt it

A backup is the entire patient database on a filesystem, outside every control
the application enforces.

```bash
python -c "
from pathlib import Path
from apps.compliance.encryption import encrypt_file
encrypt_file(Path('dx.dump'), Path('dx.dump.dx'), 'your passphrase')
"
```

AES-256-GCM with scrypt key derivation. It detects tampering and truncation as
well as protecting confidentiality — for a clinical archive, knowing a file is
*intact* matters as much as knowing it is private.

Read it back with `manage.py decrypt_archive`.

**Keep the passphrase somewhere other than the backup.** There is no recovery
path, by design.

### A backup you have not restored is not a backup

Rehearse a restore, on a separate machine, at least annually. Confirm the
restored system runs, the data is complete, and the audit chain verifies.

Most backup failures are discovered during the first real restore, which is the
worst possible moment.

## Restoring

Restoring requires one step that is easy to miss.

The audit tables are protected by database triggers refusing `UPDATE`, `DELETE`
and `TRUNCATE`. A restore will fail against them. Lift the protection for the
restore and reinstate it immediately:

```python
from apps.audit import protection

with protection.unprotected(reason="restore from backup"):
    ...  # perform the restore
```

The context manager reinstates protection even if the restore fails.

### Afterwards, always

```bash
python manage.py verify_audit_chain --checkpoint
```

A restore replaces the trail with an earlier state. It will verify internally,
but its head differs from the last checkpoint — so record a new checkpoint and
note in your records that a restore took place. Otherwise a later reviewer sees
an unexplained discontinuity.

## The audit worker

```bash
python manage.py audit_worker --verify-interval 3600
```

Run it under a process supervisor. It replays anything that could not be written
and re-verifies the chain on a schedule.

## Retention

Keep backups at least as long as the records they contain — see
[record retention](/help/administration/record-retention/). A backup regime
that keeps 30 days does not satisfy a two-year record requirement.

Store at least one copy off-site. A fire that destroys the laboratory destroys
the server room.
