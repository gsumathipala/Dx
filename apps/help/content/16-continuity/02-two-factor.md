---
title: Two-factor authentication
summary: Setting up an authenticator, what it protects against, and what to do if you lose your phone.
audience: scientist, medic, manager, clerk, phlebotomist
keywords: MFA, two-factor, 2FA, authenticator, TOTP, recovery codes, SSO, tutorial
---

## What it protects against

A stolen or phished password. That is the whole claim, and it is worth being
precise about it.

It does **not** protect a workstation you walked away from, or a session
somebody stole after you signed in. The idle timeout and signing out
deliberately are what cover those.

It is required for roles that can change who else has access — somebody who can
create an administrator account is a far more valuable target than somebody who
can enter a potassium.

## Tutorial: setting it up

**My account → Two-factor** (or Settings → search "two-factor").

### 1. Add the key to an authenticator

Use any authenticator app: Microsoft Authenticator, Google Authenticator,
1Password, Authy. They all implement the same standard, so it does not matter
which.

The screen shows a key in blocks of four. Type it into your app, or — if you
are reading this on the phone itself — open the enrolment link and the app
takes it.

### 2. Prove it works

Enter the six-digit code your app shows. **Nothing changes about how you sign
in until you do this**, so a key you failed to scan cannot lock you out.

### 3. Save your recovery codes

You get ten. Each works once. **Copy them now** — they are stored hashed and
cannot be shown again.

Put them somewhere you can reach without your phone, and not in the same place
as your password. Printed and in a drawer at home is a perfectly good answer.

## Signing in afterwards

Username and password as usual, then a code. You are not signed in between
those two steps — your password being accepted does not give you a session.

If the code is refused, the usual cause is your phone's clock. Turn on
automatic time setting.

## If you lose your phone

Sign in with a **recovery code** instead of a six-digit code. It works once and
tells you how many you have left.

Then go straight to **Two-factor → set up again** with your new device, and
generate a fresh set of recovery codes. The old set stops working.

**This is why recovery codes exist.** Without them, getting back in means an
administrator turning off your second factor — which is a social-engineering
route straight through the control. "I've lost my phone, can you disable my
MFA" is a phone call an attacker can make too.

## Turning it off

Possible only if your role does not require it, and requires both your password
and a current code. Somebody who has stolen your session should not be able to
quietly turn it off, which would otherwise be the first thing they did.

## Single sign-on

If your organisation has connected its identity provider, the sign-in page
offers **Sign in with** your organisation account. Your password and second
factor are then your organisation's, not this system's.

Two things are worth knowing:

* **The installer account never uses single sign-on.** It signs in locally, on
  purpose — it is the account you need when single sign-on is what has broken.
* **What you may do here is decided here.** Your identity provider says who you
  are; your role comes from an explicit map an administrator maintains. A group
  being renamed in the directory does not silently change what you can do to
  patient records.
