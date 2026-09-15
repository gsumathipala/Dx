---
title: Chain integrity
summary: How hash chaining makes tampering detectable, how to verify it, and what to do if it fails.
audience: manager, administrator
keywords: hash chain, integrity, tamper, verification, sha-256, checkpoint, blockchain
---

## The problem it solves

An audit trail is only worth something if you can show it was not edited.
Permissions do not achieve that: whoever administers the database can change
rows, and a changed row looks exactly like an original one.

## How chaining works

Each entry includes the hash of the entry before it:

```
hash(n) = SHA-256( contents of entry n  ‖  hash(n−1) )
```

Every entry therefore depends on every entry before it. Changing entry 500
changes its hash, which breaks entry 501's recorded predecessor, and so on to
the end.

You cannot alter one entry quietly. You would have to recompute every
subsequent hash — and the head hash, which is checkpointed and can be recorded
elsewhere, would still differ.

This is the same construction as a blockchain, without the distributed
consensus: the tamper-evidence comes from the chaining, not from a network.

## What is protected

Everything with evidential weight: sequence, timestamp, actor and role, record
type and id, action, field changes, reason, source, IP, request id, session.

Anything omitted would be alterable without detection, which is why the covered
set is deliberately wide.

## Verifying

**Chain Integrity** (managers and the installer) shows the head, the last
verification, whether the recorder is running, and any open alerts.

**Verify chain now** recomputes every hash and reports.

From the command line:

```bash
python manage.py verify_audit_chain --checkpoint
```

It exits non-zero on failure, so it can gate a nightly job. The audit worker
also verifies on a schedule.

## Checkpoints

Each verification records a checkpoint: the head sequence, the head hash, the
count and the outcome. A checkpoint proves the trail was intact at a known
moment without re-reading the whole history later.

For stronger evidence, record the head hash somewhere outside the system —
a compliance log, an email to the quality manager. Then even a total
compromise cannot rewrite history undetected, because the external record
disagrees.

## If verification fails

The report names the **exact entry**:

> Tampered content at #4,512 (UPDATE laboratory.Result/a3f9…): recomputed
> 17a5ce13… but stored d892210e…

That is the entry whose content no longer matches its hash.

**Treat it as a security incident.**

1. **Do not attempt to repair it.** There is no legitimate repair; an attempt
   would itself alter the trail.
2. **Preserve everything.** Do not restore over the database.
3. **Escalate** to the laboratory director and whoever is responsible for
   information security.
4. **Establish the window.** The last successful checkpoint bounds when it could
   have happened.
5. **Consider the clinical consequence.** If audit records were altered,
   patient data may have been too.

An integrity alert cannot be cleared by acknowledgement. Acknowledging records
that someone has seen it; the discrepancy remains.

## Two causes that are not attacks

**A restore from backup** replaces the table with an earlier state, which
verifies internally but has a different head from the checkpoint. Re-verify and
record a new checkpoint immediately after any restore.

**A deliberate reset** archives the old chain and starts a new one whose first
entry records the previous chain's length and head hash — so the two reconcile
rather than leaving an unexplained empty table.
