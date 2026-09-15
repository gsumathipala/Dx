---
title: Roles and permissions
summary: What each role can do, why the boundaries sit where they do, and how separation of duties works.
audience: everyone
keywords: roles, permissions, access, installer, separation of duties, rbac
---

## Why roles exist

Access is granted by role, and the boundaries are not arbitrary. Two principles
shape them.

**Least privilege.** Nobody holds authority they do not need. A phlebotomist
does not configure clinical rules; an administrator does not need to be a
biomedical scientist to manage accounts.

**Separation of duties.** Some pairs of powers must not sit with one person.
The clearest example: whoever *maintains* the system should not thereby be able
to *read patient records*. Concentrating both in one account means a single
compromised login exposes everything.

## The roles

| Role | Purpose |
| --- | --- |
| **Installer** | Commissions and maintains the system. No clinical access whatsoever. |
| **Administrator** | Everything clinical and administrative. |
| **Laboratory manager** | Laboratory configuration, compliance oversight, verification, KPIs. |
| **Biomedical scientist** | Result entry, technical validation, clinical verification, QC. |
| **Medical officer** | Clinical verification, critical value documentation, reports. |
| **Clerk** | Accessioning, reception, phlebotomy scheduling, patient registration. |
| **Phlebotomist** | Phlebotomy rounds and collection. |

## Roles are not a ladder

It is tempting to picture roles as a hierarchy with the most powerful at the
top. That picture is wrong here, and the installer is why.

The installer holds the **highest system authority** — it can reset the entire
database, which nobody else can — and the **lowest clinical authority**: it
cannot open a single patient record. Authority runs along two independent axes,
not one.

```
                 clinical authority
                        ▲
      administrator ●   │
                        │   ● manager
                        │        ● scientist / medic
                        │             ● clerk / phlebotomist
  ──────────────────────┼──────────────────────────► system authority
                        │
          installer ●   │   (high system, zero clinical)
```

## What a control looks like when it stops you

Some actions are refused even to someone whose role would otherwise allow them,
because a regulatory control applies:

| Refusal | Basis |
| --- | --- |
| You cannot verify a result you entered | CLIA independent review |
| Results blocked while QC is failing | CLIA 42 CFR §493.1256 |
| No current competency for this test | CLIA 42 CFR §493.1451 |
| Password required before signing | 21 CFR Part 11 §11.200 |

These are not permission problems and cannot be fixed by changing your role.
See [When the system stops you](/help/troubleshooting/when-the-system-stops-you/).

## Changing someone's role

Administrators and the installer can change a role from **Settings → Users**.
The change is recorded in the audit trail.

The installer role cannot be granted through the interface — there is exactly
one installer account, created during installation.
