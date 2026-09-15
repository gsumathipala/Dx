---
title: Keyboard shortcuts and quick reference
summary: Shortcuts, status colours, order states and the commands administrators need.
audience: everyone
keywords: keyboard, shortcuts, reference, quick, commands, cheatsheet
---

## Keyboard

| Key | Where | Does |
| --- | --- | --- |
| `/` | Anywhere | Jump to the search box |
| `Enter` / `↓` | Result entry | Next value |
| `↑` | Result entry | Previous value |
| `Ctrl` + `Enter` | Result entry | Save |
| `Tab` | Forms | Next field |

Result entry focuses the first value automatically, so a panel can be entered
without the mouse.

## Search

| Type | Gets |
| --- | --- |
| Exact accession number | That order, at its current stage |
| Exact MRN | That patient |
| Surname | A list of matches |

Barcode scanners work with no configuration — they type and press Enter.

## Order states

| State | Meaning |
| --- | --- |
| Pending | Accessioned, specimen not received |
| Received | Specimen accepted |
| Resulted | Values entered, not authorised |
| Technically Validated | Analytical run accepted |
| Completed | Verified and released |
| Rejected | Specimen unsuitable |

## Status colours

| Colour | Meaning |
| --- | --- |
| Green | Complete, passed, acceptable, active |
| Amber | In progress, warning, approaching a limit |
| Red | Failed, rejected, breached, critical |
| Grey | Draft, scheduled, not applicable |

## Result flags

| Flag | Meaning |
| --- | --- |
| Critical Low / High | Beyond the panic limit — notification required |
| Low / High | Outside the reference interval |
| Normal | Within, or no applicable bound |

## Administrator commands

```bash
# Daily operation
python manage.py runserver
python manage.py audit_worker --verify-interval 3600

# Integrity
python manage.py verify_audit_chain --checkpoint

# Accounts
python manage.py create_installer --username installer
python manage.py reset_installer_password

# Data
python manage.py seed_demo
python manage.py seed_demo --reset
python manage.py reset_data --dry-run
python manage.py reset_data --confirm "ERASE ALL DATA" --archive-to backups/
python manage.py import_legacy --sqlite sqlite_v2.db --dry-run
python manage.py decrypt_archive backup.jsonl.dx

# Maintenance
python manage.py migrate
python manage.py collectstatic
python manage.py check --deploy
python manage.py test tests
```

## The instrument server

```bash
cd instrument_server
INSTRUMENT_INGEST_TOKEN=... python -m dx_instrument.cli --port 5150 --protocol astm
python -m dx_instrument.simulator 2026-09-15-0007 --protocol astm
```

## Where things live

| Looking for | Go to |
| --- | --- |
| Work waiting for you | Dashboard |
| An order | Search, or Worklist |
| A released report | Reports |
| Who changed something | Audit Trail, or History on the record |
| Any configuration screen | Settings (searchable) |
| What is outstanding for compliance | Compliance |
