---
title: Resetting the system
summary: Erasing all data to commission a machine, the safeguards, and why a reset cannot be silent.
audience: administrator
keywords: reset, erase, commission, install, wipe, archive, fresh
---

## When to use it

Commissioning a machine: install, load demonstration data, confirm everything
behaves, then erase it to hand over an empty system.

> **This is not recoverable from inside the application. Take a database backup
> first.**

## Doing it

```bash
python manage.py reset_data --dry-run                 # review what would go
python manage.py reset_data --confirm "ERASE ALL DATA" \
    --archive-to backups/ --encrypt-archive "a passphrase"
python manage.py create_installer --username installer
```

| Option | Effect |
| --- | --- |
| `--dry-run` | Report only; delete nothing |
| `--confirm "ERASE ALL DATA"` | Required, exactly |
| `--archive-to DIR` | Where to write the audit archive |
| `--encrypt-archive PASSPHRASE` | Encrypt it — strongly advised |
| `--keep-users` | Leave accounts, departments and competency |
| `--keep-audit` | Erase data, keep the trail |
| `--i-understand-this-is-production` | Required when `DEBUG` is off |

## Why it cannot be silent

A reset is exactly what someone would reach for to erase evidence. So three
things happen around it:

**The trail is verified and archived first.** The archive header records the
event count, the head hash and whether the chain verified — so you know the
archive was intact when taken.

**The new chain records the reset.** Its first entry says who ran it, when, how
many entries the previous chain held, and the hash it ended on.

**The two reconcile.** The archive's head hash and the new entry's
`previous_chain_head_hash` match. An inspector can confirm nothing was quietly
removed.

An empty audit table with no explanation is indistinguishable from a cover-up.
The command will not produce one.

## Afterwards

A full reset leaves **no accounts**. Create one before signing in:

```bash
python manage.py create_installer --username installer
```

Then sign in as the installer and add staff from Settings → Users.

## Keep the archive

The archived trail is the only record of everything that happened before the
reset. Store it with your backups, for at least the audit retention period.

If you encrypted it, store the passphrase separately and durably. An encrypted
archive whose passphrase is lost is a deleted archive.
