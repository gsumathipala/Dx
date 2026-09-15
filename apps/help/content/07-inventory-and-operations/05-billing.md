---
title: Billing
summary: The charge catalogue, raising invoices, and where billing touches clinical work.
audience: clerk, manager
keywords: billing, invoice, charge, cpt, price, catalogue
---

## The catalogue

**Settings → Billing catalogue** holds chargeable items: a code — typically
CPT-4 in the US, or a local schedule elsewhere — a name, a price, and the tests
the item covers.

Linking items to tests is what lets an invoice be raised from an order without
anyone deciding what to charge.

## Raising an invoice

An invoice is raised against a completed order. Each test with a linked
catalogue item becomes a line, and the total is their sum.

If **no** catalogue entry covers the tests on an order, you are told rather than
given a zero invoice. A zero invoice looks like a free test; an explicit refusal
looks like missing configuration, which is what it is.

## Invoice lines

Lines are held individually — code, description, quantity, unit price — rather
than as a blob of text.

That matters for anything beyond printing one invoice: revenue by test, the
effect of a price change, a payer query about one line. A JSON blob makes all of
those a parsing exercise.

## Where billing meets clinical work

**Reflex tests are billable.** A rule that adds a test adds a charge. Agree
reflex algorithms with whoever handles billing as well as with clinicians.

**Rejected specimens.** Decide your policy: most laboratories do not charge for
a test not performed, but a recollection is real work.

**Medical necessity.** In some systems payment depends on the diagnosis
justifying the test, which requires a diagnosis code on the order. Dx does not
currently record ICD-10 codes — if your payers require them, that is a gap to
close before go-live.

## Keep it separate from clinical decisions

A test should be done because it is indicated, and charged because it was done —
in that order. Nothing in Dx makes a clinical decision depend on a charge, and
nothing should.

Billing pressure on test selection is both a clinical and a legal problem, and
the separation is worth defending explicitly.
