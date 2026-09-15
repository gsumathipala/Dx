---
title: Signing in and your account
summary: Passwords, lockouts, automatic sign-out, and why accounts are never shared.
audience: everyone
keywords: password, login, lockout, timeout, account, security
---

## Your account is yours alone

Every account belongs to one named person. Accounts are never shared, and there
is no generic "lab" login.

This is not administrative fussiness. Every result you enter, every validation
you perform and every report you release is recorded against your name, and
your password acts as your **electronic signature**. If two people share an
account, nobody can say which of them authorised a result — and a signature
that could have been anyone's is not a signature at all.

> **21 CFR Part 11 §11.10(d)** requires system access to be limited to
> authorised individuals, and §11.200 requires that an electronic signature be
> used only by its genuine owner.

## Signing in

Go to the address your laboratory uses and enter your username and password.

If the details are wrong, the message is deliberately vague — it does not say
whether the username exists. That stops someone probing for valid usernames.

## Changing your password

Use **My password** at the bottom of the sidebar. You will need your current
password, and the new one must:

- be at least 8 characters,
- differ from your last 5 passwords,
- not be a commonly used password, and
- not be entirely numeric.

Anyone can change their own password at any time, including the installer.

### Choosing a good one

Length matters more than punctuation. A passphrase of four unrelated words is
both easier to remember and harder to guess than a short string with symbols
substituted for letters — `correct-horse-battery-staple` beats `P@ssw0rd!`
comfortably.

Never reuse a password you use elsewhere. If another site is breached, the
attacker tries the same password against everything they can find.

## Being asked to change it immediately

Two situations force a change before you can do anything else:

**Your password has expired.** Passwords age out after 90 days by default.

**An administrator issued you a temporary one.** A temporary password is known
to somebody other than you, so it cannot remain in use — otherwise the
administrator could act as you, and your signature would no longer be yours.

## If you are locked out

Five failed attempts lock the account for 30 minutes. This slows an attacker
guessing passwords to a rate that makes guessing pointless.

Wait for the lock to expire, or ask an administrator to reset your password —
a reset clears the lock.

## Automatic sign-out

After 20 minutes of inactivity you are signed out. A laboratory workstation is
often in a shared space, and an unattended signed-in screen is an open door to
patient records.

Anything typed but not saved is lost, so **save before you walk away**.

## Signing out

Use **Sign out** at the bottom of the sidebar. Do it whenever you leave a
shared workstation, even briefly — do not rely on the timeout.

## What is recorded

| Event | Recorded |
| --- | --- |
| Successful sign-in | Yes |
| Failed sign-in | Yes, including the username tried |
| Sign-out | Yes |
| Password change | Yes — the fact, never the password |
| Account lock | Yes |

Passwords themselves are stored only as a one-way hash. Nobody — not an
administrator, not the installer, not whoever has the database — can read your
password back out.
