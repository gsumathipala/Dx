---
title: "Tutorial: managing user accounts"
summary: Adding staff, issuing temporary passwords, suspending accounts and what happens when you cannot delete one.
audience: administrator
keywords: tutorial, users, accounts, password, reset, disable, delete, suspend
---

## Who can do this

**Administrators** and the **installer**, at Settings → Users.

---

## Adding someone

1. **Users → New user**.
2. Enter username, full name, role, department and email.
3. **Save.** The account now exists with **no usable password**.
4. Use **Reset password** to give them a temporary one.

The installer role is not offered — there is one installer account, created
during installation.

### Choosing a username

Pick a convention and keep it: initial plus surname, or employee number. It
appears throughout the audit trail forever, so it should identify the person
unambiguously years later.

Never reuse a username. `jsmith` belonging to two people at different times
makes the audit trail ambiguous exactly when it matters.

---

## Resetting a password

1. Find the account → **Reset password**.
2. Enter a temporary password twice.
3. **Give a reason.** It is recorded — *"forgotten password, identity confirmed
   in person"*.
4. Hand it over by a channel you trust. **Not** the email account you are
   restoring access to.

They must change it at their next sign-in, so **you never know their working
password**. That is precisely what makes their electronic signature theirs and
not yours.

Confirm who you are speaking to before resetting. A telephone call claiming to
be a colleague locked out is the oldest attack there is.

The action does not appear on the installer account.

---

## Suspending an account

**Disable**. They cannot sign in until re-enabled. Nothing they have done
changes — results, signatures and audit entries are untouched.

Use it for leave, suspension, or anyone who has left. It works on **every**
account including the installer's.

You cannot disable your own account.

### Disable promptly when someone leaves

On their last day, not at the end of the month. A live account belonging to
someone who no longer works there is the commonest avoidable access risk, and it
is a standing inspection finding.

---

## Deleting an account

**Delete**. If the person has ever signed or authorised anything, deletion is
**refused and the account disabled instead**, and you are told so.

That is not a limitation to work around. A signature has to keep naming a real
person — a report signed by a deleted user is a report signed by nobody.

In practice: **disable is the normal outcome**, and delete applies mainly to an
account created in error that was never used.

---

## Everything here is recorded

Every reset, suspension, re-enablement and deletion is written to the audit
trail against **your** account, with the reason you gave.

Use **History** on any account to see everything that ever happened to it —
useful when an inspector asks how access was managed, and when investigating
whether an account was misused.

---

## Reviewing access periodically

Every few months, look at the list and ask:

- Is everyone here still employed?
- Does everyone still need the role they have?
- Are there accounts nobody has signed into for months?
- Is anybody sharing?

Access accumulates. People change roles and keep the old permissions; leavers
are forgotten. A periodic review is the only thing that reverses the drift.
