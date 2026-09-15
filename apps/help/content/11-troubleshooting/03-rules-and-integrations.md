---
title: When a rule or an integration misbehaves
summary: Why a rule did not fire, why a result was not released, and why an integration went quiet.
audience: scientist, manager, medic
keywords: troubleshooting, rule did not fire, autoverification refused, webhook failing, interface silent
---

## "My rule did not fire"

Work down this list. It is in order of how often each is the cause.

### 1. Is it approved?

**Settings → Decision rules** shows the status. *Draft v2 — awaiting approval*
means it is not running. Editing a rule withdraws its approval; this catches
almost everybody the first time.

### 2. Is it active?

A rule can be approved and disabled.

### 3. Did an earlier rule stop on match?

A higher-priority rule with **stop on match** ticked prevents every later rule
running for that result. Check the firing log for what did fire.

### 4. Are the conditions actually true?

Use **Try it against a real order** on the rule's page, with the accession
number that should have matched. The simulation shows each condition, the fact
it saw, and whether it held.

The two usual culprits: a threshold in the wrong units, and a text comparison
against a value that is not spelled the way you assumed.

### 5. Is a fact unavailable?

A fact that could not be measured makes every comparison **false**. A rule
conditioned on the previous result will not fire on a patient's first ever
sample. Use *is blank* if absence is what you meant to test.

### 6. Is it scoped to the right test?

A rule with **applies to** set fires only for that analyte.

---

## "A result should have been autoverified and was not"

Open the [rule firing log](/help/rules-and-automation/autoverification/) and
find the entry. It lists **every** refusal, not just the first:

| Refusal | What to do |
| --- | --- |
| `… is not approved for autoverification` | Tick *auto verify permitted* on the test definition, once validated |
| `Quality control: No quality control has been run…` | Run QC for that analyte |
| `Quality control: The most recent QC run … failed` | Investigate, repeat QC |
| `The result is above/below the reference interval` | Working as intended |
| `Critical values are never autoverified` | Working as intended, permanently |
| `A delta check flagged this result` | Working as intended — somebody should look |
| `The result carries flags` | Check which; a rule may have added one |
| `No reference interval is defined for …` | Define one; "normal" has no meaning without it |
| `The specimen was received as Marginal` | Working as intended |
| `This order has an unresolved item on the exception queue` | Clear the exception |
| `Autoverification is disabled for this installation` | `RULES_ALLOW_AUTO_VERIFICATION=0` is set — ask your administrator whether that is deliberate |

If there is **no entry at all**, the rule did not match. Go back to the section
above.

---

## "An interface has gone quiet"

An enabled interface that sends nothing for over an hour raises an item on the
[exception queue](/help/rules-and-automation/exception-queue/).

Check, in order:

1. Is the analyser running and connected?
2. Is the instrument server process running?
3. Can the instrument server reach the LIS? Its log says so on every attempt.
4. Is anything spooled? The instrument server writes undelivered payloads to a
   spool file and replays them; a growing spool means the LIS is unreachable,
   not that the analyser is silent.

Results are **not lost** while the LIS is unreachable — that is what the spool
is for.

---

## "An order from the hospital did not arrive"

**Settings → Instrument messages** shows every inbound message, including
refused ones, with the reason.

| Reason | Cause |
| --- | --- |
| `The PID segment carries no medical record number` | The sending system omitted PID-3 |
| `A new patient needs a date of birth` | PID-7 empty on a patient we do not already hold |
| `None of the requested tests could be matched` | The codes in OBR-4 are not in your catalogue, under any of code, LOINC or alternate identifier |
| `Order control code X is not supported` | Only `NW`, `SN`, `OK`, `CA`, `OC`, `CR`, `HD` are acted on |
| `Message type X is not supported` | Only ORM, OML and ADT |

A refused message also raises an exception queue item, so it should not be a
surprise.

If a message does not appear in the log **at all**, it never reached Dx. Check
the integration engine's own outbound log and the bearer token.

---

## "A webhook subscriber is not being called"

**Settings → Webhooks** lists recent deliveries.

| What you see | Cause |
| --- | --- |
| Nothing at all, and deliveries are pending | The `deliver_webhooks` worker is not running |
| `retrying` with a connection error | The subscriber's URL is unreachable |
| `retrying` with a 4xx | The subscriber is rejecting the payload — usually a signature check the receiver has got wrong |
| `failed` | Six attempts exhausted |
| The webhook is inactive with a *disabled automatically* reason | Twenty consecutive failures |

The most common receiver-side bug is verifying the signature against a
re-serialised body. Verify against the **raw bytes**.

---

## "An API client is getting 403"

The error names the missing scope:

```json
{"error": {"code": "insufficient_scope",
           "message": "This client lacks the scope(s): results:read.",
           "required": ["results:read"]}}
```

Either widen the scope at **Settings → API clients**, or — more often the right
answer — find out why the integration is asking for something outside its
purpose.

A `429` means the client is over its rate limit. Raise the limit only after
establishing the client is not simply looping.
