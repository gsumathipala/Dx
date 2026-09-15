---
title: Common problems
summary: Symptoms with their usual causes, for laboratory staff and administrators.
audience: everyone
keywords: problems, faq, symptoms, causes, help, fix
---

## I cannot find an order

- **Search the accession number exactly.** Partial numbers return a list;
  exact ones navigate.
- **Check it was accessioned.** If it never was, it does not exist.
- **Check the status filter** on the worklist — completed orders are not listed
  there. Use **Reports**.

## A result will not save

- **Check the field.** Text in a numeric field is stored as text and not
  flagged; that is allowed, but check it is what you meant.
- **Check the test belongs to the order.** A test not on the order cannot be
  resulted against it.
- **Read the message at the top.** A refused control explains itself.

## The previous value column is empty

Either the patient has no earlier numeric result for that test, or the earlier
result is outside the lookback window, or it was recorded as text.

## A delta check did not fire when I expected

- The previous result must be **genuinely earlier** than this order.
- It must be within the rule's **lookback** window.
- Both values must be **numeric**.
- Check **direction**: a decrease-only rule ignores an increase.
- Check the rule is **enabled** and attached to the right test.

## A critical value was not raised

- Check the test has `panicLow` / `panicHigh` in its reference range.
- A demographic interval for the patient's age or sex may override the default —
  check that one too.
- A notification already pending for the same order and test is not duplicated.

## Reflex testing did not add the test

- A rule fires **once per order**.
- Check the operator and threshold.
- Check the rule is enabled.
- A rule cannot add the test that triggered it.

## QC keeps failing on a method that seems fine

Usually the **target SD is too tight** — established from too few runs, or from
a different reagent lot.

Re-establish the mean and SD over at least 20 runs on your current lot and
instrument. Do **not** simply widen the SD to stop the failures: that removes
the check rather than fixing it.

## An instrument interface has gone quiet

**Settings → Instrument messages** first. See
[instrument interfaces](/help/interoperability/instrument-interfaces/) for the
symptom table. The commonest cause is an accession number mismatch.

## A report was not delivered

- Check the **delivery queue** for a failure.
- Check the requester's delivery preference and contact details.
- Check a distribution rule exists for that requester.

## Reagent stock looks wrong

- Consumption decrements only when a result is entered for a test **explicitly
  linked** to that reagent.
- Expired reagents are not consumed.
- Record deliveries and stocktakes as adjustments; stock that drifts is worse
  than no record.

---

## For administrators

### "connection to server … failed"

PostgreSQL is not running. Start it as your installation expects.

### "Missing staticfiles manifest entry"

Running with `DEBUG=False` without having collected static files. Run
`python manage.py collectstatic`.

### "relation … does not exist"

Migrations have not been applied. Run `python manage.py migrate`.

### "audit_events is append-only"

The audit protection working as designed. A restore requires lifting it
deliberately — see
[backup and restore](/help/administration/backup-and-restore/).

### Nobody can sign in after a reset

A full reset removes every account:
`python manage.py create_installer --username installer`

### Chain verification fails

Treat it as a security incident. See
[chain integrity](/help/security-and-audit/chain-integrity/). Do not attempt to
repair it.
