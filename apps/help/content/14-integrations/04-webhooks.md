---
title: Webhooks
summary: Telling another system something happened, instead of it asking repeatedly.
audience: manager
keywords: webhook, events, signature, HMAC, subscription, tutorial, integration
---

## Polling versus being told

A system that needs to know when a report is ready has two options. It can ask
every thirty seconds — which is thousands of requests a day, almost all of them
answered "nothing new" — or it can be told.

A webhook is being told.

## Events

| Event | Fired when |
| --- | --- |
| `order.created` | An order is accessioned, however it arrived |
| `order.completed` | Every analyte on an order is verified |
| `result.entered` | A result is entered or corrected |
| `result.verified` | A result is clinically verified |
| `report.released` | A report is released for distribution |
| `report.amended` | A released report is corrected |
| `critical_value.raised` | A result breaches a panic limit |
| `exception.raised` | An item reaches the exception queue |
| `qc.failed` | A quality control run fails |

## What a payload contains — and does not

**Direct identifiers are stripped by default.** The patient's surrogate id
survives; the MRN, name, date of birth and contact details are replaced with
`[redacted]`.

A subscriber that is entitled to the detail fetches it over the API, where the
read is authenticated, scoped and recorded as a disclosure. A webhook body, by
contrast, lands in somebody's application log, their monitoring system, and
whatever else is between here and there.

A subscription may set **include identifiers** where the receiving system is
itself a covered entity and the disclosure is accounted for. It is off by
default because that is a decision somebody should have to make deliberately.

## Signing

Every delivery carries:

```
X-Dx-Event: result.verified
X-Dx-Delivery: 1f0c…
X-Dx-Signature: t=1789567800,v1=6c3f…
```

`v1` is an HMAC-SHA256 of the timestamp and the raw body, using the
subscription's secret. The receiver recomputes it, compares in constant time,
and rejects anything whose timestamp is more than five minutes old — which
makes a captured payload useless to replay.

**A subscriber that does not verify the signature is trusting anyone who can
reach its URL.** Tell whoever is building the receiving end.

The signing secret is shown once, when the subscription is created.

## Delivery

* **HTTPS only.** An `http://` subscription is refused at creation.
* **Fired after commit.** A rolled-back transaction never emits an event
  claiming something happened.
* **Retried with backoff** — roughly 30 seconds, 2 minutes, 8 minutes, 30
  minutes, 2 hours — up to six attempts.
* **Never dropped silently.** A subscriber that has failed twenty times in a
  row is disabled and raises an item on the exception queue.

That last point matters more than it looks. An integration that quietly stopped
working is how a ward finds out about a critical result by telephone three days
later.

## Tutorial: notify the ward when a report is ready

### 1. Create the subscription

**Settings → Webhooks → New**.

| Field | Value |
| --- | --- |
| Name | `Ward 7 report notifier` |
| URL | `https://ward7.example.org/hooks/dx` |
| Events | `report.released` |
| Include identifiers | leave unticked |

### 2. Copy the signing secret

Shown once, on save.

### 3. The receiving end verifies

```python
import hashlib, hmac, time

def verify(secret, body, header, tolerance=300):
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    timestamp = int(parts["t"])
    if abs(time.time() - timestamp) > tolerance:
        return False
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

Note `body` is the **raw bytes**, before any JSON parsing. Re-serialising
changes the bytes and the signature will not match.

### 4. Check it is working

**Settings → Webhooks** lists recent deliveries with their status, attempt
count and response code. A column of `delivered` and a failure count of zero is
what you want.

## Running the deliverer

Deliveries are performed by a worker, so a slow subscriber cannot stall result
entry. Your administrator runs:

```bash
python manage.py deliver_webhooks --forever --interval 15
```

If nothing is being delivered and the queue is growing, that process is not
running.
