---
title: Configuration and the settings index
summary: Where each setting lives, who may change it, and what a change means.
audience: manager, administrator
keywords: settings, configuration, index, search, admin
---

## The settings index

**Settings** is a searchable index of every configuration screen, grouped by
area. Type `delta`, `calibration`, `retention` or `loinc` rather than scanning
a list.

| Group | Contains |
| --- | --- |
| Test catalogue | Test definitions, calculated tests, demographic intervals, LOINC |
| Clinical rules | Delta checks, reflex rules, notifiable conditions |
| Quality | QC materials and targets, equipment, rejection criteria |
| Compliance | Proficiency testing, validation, risk, change control, training, competency, retention |
| Access and privacy | Users, departments, queues, PHI access, disclosures, chain integrity |
| Operations | Workstations, routing, TAT thresholds, worksheets, storage, inventory |
| Reporting | Documents, requesters, distribution, delivery, billing |
| System | Interfaces, instrument messages, alerts, configuration, backup, KPIs |

An **installer** sees only the system entries: laboratory configuration is the
laboratory's decision.

## Two kinds of setting

**In-application configuration** — the test catalogue, clinical rules, QC
targets. Changed through the interface by managers and administrators, recorded
in the audit trail.

**Environment settings** — database credentials, enforced controls, password
policy, session timeouts. Set in `.env`, require a restart, and are not
changeable from the interface.

The split is deliberate. Anything that could disable a regulatory control is
outside the application, so it cannot be turned off from a screen under
pressure.

## Enforced controls

| Setting | Default | Effect if off |
| --- | --- | --- |
| `ENFORCE_QC_LOCKOUT` | On | Results release despite failed QC |
| `ENFORCE_COMPETENCY_GATING` | On | Anyone may validate any test |
| `ENFORCE_SELF_VERIFICATION_BLOCK` | On | One person may enter and verify |
| `REQUIRE_REAUTH_FOR_SIGNATURE` | On | Signatures apply without a password |

Their state is shown on the compliance dashboard, so a relaxation is visible
rather than quiet.

There is a legitimate reason to turn one off — commissioning a system with no
competency records yet — and it should be temporary, documented, and reversed.

## Changing configuration is a change

Editing a critical limit, a delta rule or a reference interval changes how
results are interpreted for every patient afterwards.

Significant changes should carry a
[change control record](/help/administration/change-control/) and, where they
affect result production, evidence they were validated.
