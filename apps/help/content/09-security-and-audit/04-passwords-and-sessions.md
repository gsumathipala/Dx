---
title: Passwords, sessions and account security
summary: The controls protecting accounts, and the reasoning behind each setting.
audience: everyone
keywords: password, session, lockout, expiry, timeout, security, part 11
---

## The controls

| Control | Default | Setting |
| --- | --- | --- |
| Minimum length | 8 characters | Django validators |
| Reuse prevention | Last 5 | `PASSWORD_HISTORY_DEPTH` |
| Expiry | 90 days | `PASSWORD_EXPIRY_DAYS` |
| Lockout threshold | 5 attempts | `ACCOUNT_LOCKOUT_THRESHOLD` |
| Lockout duration | 30 minutes | `ACCOUNT_LOCKOUT_MINUTES` |
| Idle sign-out | 20 minutes | `IDLE_TIMEOUT_MINUTES` |
| Re-authentication at signing | On | `REQUIRE_REAUTH_FOR_SIGNATURE` |

> **21 CFR Part 11 §11.300** requires controls over identification codes and
> passwords: periodic ageing, safeguards against unauthorised use, and
> transaction safeguards.

## Why each exists

**Reuse prevention** stops the cycle of alternating between two passwords, which
defeats expiry entirely.

**Expiry** limits how long a compromised password stays useful. Current thinking
questions frequent forced rotation — it pushes people toward predictable
patterns like `Summer2026!` — so if you lengthen the interval, compensate with
length requirements and monitoring rather than simply relaxing.

**Lockout** makes guessing pointless. Five attempts then thirty minutes limits an
attacker to a handful of guesses an hour.

**Idle sign-out** addresses the unattended workstation, which in a laboratory is
usually in a shared space.

**Re-authentication at signing** is the one people ask about. Being signed in
proves you were there earlier; it does not prove you are the person clicking
now. An electronic signature has to mean the named person authorised *this*, at
*this moment*.

## How passwords are stored

Hashed with bcrypt, one-way. Nobody can read a password out — not an
administrator, not the installer, not someone with the database.

A password reset therefore **sets a new one**; it never reveals the old.

## What is recorded

| Event | Recorded |
| --- | --- |
| Successful sign-in | Yes |
| Failed sign-in | Yes, with the username attempted |
| Sign-out | Yes |
| Password change | Yes — the fact, never the value |
| Administrator reset | Yes, with the reason given |
| Account lock | Yes |
| Account disabled or enabled | Yes |

Failed sign-ins are worth watching: a burst against one account is an attack; a
burst across many is a credential-stuffing attempt.

## Changing the settings

These are environment settings, not in-application configuration. Changing them
is a system change and should carry a
[change control record](/help/administration/change-control/).

Relaxing them is a decision with consequences. The compliance dashboard shows
which enforced controls are on, so a relaxation is visible rather than quiet.
