---
title: The REST API
summary: Giving another system programmatic access — credentials, scopes, and what it can and cannot do.
audience: manager, medic
keywords: API, REST, token, scope, credential, integration, tutorial, JSON
---

## Who this is for

The hospital's **integration engine** wants HL7 and FHIR, which Dx speaks
elsewhere. The hospital's **own developers** want an ordinary JSON API: the
ward dashboard, the audit extract, the research pull.

That is what `/api/v1/` is.

Full technical reference: [`docs/API.md`](https://github.com/gsumathipala/Dx/blob/main/docs/API.md)
in the repository. This topic covers what a laboratory manager needs to decide.

## Issuing a credential

**Settings → API clients → New** (administrators only).

| Field | Why it matters |
| --- | --- |
| Name | Appears on every audit event and disclosure record |
| Organisation | The receiving organisation, named on disclosure records |
| Purpose | Required before any patient-data scope can be granted |
| Owner | The person accountable for this credential |
| Scopes | What it may do — see below |
| Rate limit | Requests per minute, default 120 |
| Expiry | Optional, and worth setting |

**The token is shown once.** Copy it then. It is stored as a password hash and
cannot be retrieved; a system that can show you a credential again stores it in
a form an attacker can use.

If it is lost, **rotate** the secret. That takes effect immediately with no
grace period — which is the point of rotating, and means you should tell the
other side first.

## Scopes

| Scope | Grants | Patient data |
| --- | --- | --- |
| `catalogue:read` | Test catalogue, LOINC, ICD-10 | No |
| `patients:read` | Demographics | **Yes** |
| `patients:write` | Register and update patients | **Yes** |
| `orders:read` | Orders and diagnoses | **Yes** |
| `orders:write` | Place orders | **Yes** |
| `results:read` | Results | **Yes** |
| `reports:read` | Reports as JSON, FHIR or HL7 | **Yes** |
| `exceptions:read` | The exception queue | **Yes** |
| `webhooks:manage` | Its own event subscriptions | No |

**Grant the least that will do the job.** A ward dashboard showing whether
results are ready needs `orders:read`, not `results:read`. HIPAA's minimum
necessary standard (45 CFR §164.502(b)) is not satisfied by "we gave them
everything and trust them".

Every read a PHI-scoped client performs is recorded as a disclosure, naming the
client and its organisation, and appears on the PHI access log alongside human
access.

## What the API cannot do

**It cannot verify, validate or release a result.**

A bearer token identifies a *system*. An electronic signature identifies a
*person* at the moment of signing, and 21 CFR Part 11 §11.200 requires one.
There is no way to hand a token the authority to sign, and none will be added.

An integration can place orders, read results and be told when things happen.
Authorising clinical work stays with people using the application.

## Tutorial: a ward results dashboard

### 1. Decide the scope

The dashboard shows whether a ward's requests are complete and, for completed
ones, the results. That needs `orders:read` and `results:read`.

### 2. Issue the credential

Name it `Ward 7 results board`, organisation and purpose filled in, expiry
twelve months, rate limit 120.

### 3. Give the developers the token, once

Separately from anything else — not in the same email as the URL.

### 4. They call it

```bash
curl -H "Authorization: Bearer 3f2a91c4de70b118.qKZ9p2vN-aXr…" \
     "https://lis.example.org/api/v1/orders/?status=Completed&since=2026-09-15T00:00:00Z"
```

```json
{
  "data": [
    {
      "accession_number": "2026-09-15-0007",
      "status": "Completed",
      "priority": "Routine",
      "patient": {"id": "8f2c…", "mrn": "MRN001", "last_name": "Doe"},
      "tests": ["GLU", "K"]
    }
  ],
  "page": {"number": 1, "size": 50, "total_pages": 1, "total_items": 1, "has_next": false}
}
```

### 5. Review it

Come back to **Settings → API clients** occasionally. Look at *last used*. A
credential nobody has used in six months should be disabled, and one whose
project ended should be deleted.

## A note on autoverified results

A result read over the API carries `"autoverified": true` when it was released
by a decision rule rather than read by a person. Anything presenting results
clinically should surface that distinction, exactly as the printed report does.
