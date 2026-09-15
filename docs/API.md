# Dx API reference and rules

What the API exposes today, and the rules any new endpoint must follow.

Read this before adding an endpoint. The rules are not style preferences — most
of them exist because the system holds patient data under CLIA, CAP, ISO 15189,
21 CFR Part 11 and HIPAA, and an API is the easiest place to lose all of that
by accident.

Related: [USER_MANUAL.md](USER_MANUAL.md) · [REGULATORY.md](REGULATORY.md) ·
[INSTALL.md](../INSTALL.md)

---

## Contents

1. [Status of the API](#1-status-of-the-api)
2. [The rules](#2-the-rules)
3. [Authentication](#3-authentication)
4. [Conventions](#4-conventions)
5. [Errors](#5-errors)
6. [The v1 API](#6-the-v1-api)
7. [Service endpoints](#7-service-endpoints)
8. [Webhooks](#8-webhooks)
9. [Adding an endpoint: checklist](#9-adding-an-endpoint-checklist)

---

## 1. Status of the API

Dx is a server-rendered application with a **versioned JSON API alongside it**.

| Surface | Base | Authentication |
| --- | --- | --- |
| Public API | `/api/v1/` | Client credentials (bearer token), scoped |
| Instrument middleware | `/api/middleware/` | Shared bearer token |
| Inbound HL7 v2 | `/api/middleware/hl7/` | Shared bearer token |
| Host query | `/api/middleware/query/` | Shared bearer token |
| FHIR / HL7 export | `/interop/` | Session |
| Audit verification | `/audit/api/verify/` | Session |
| Health probe | `/healthz/` | None |

There is no GraphQL surface, and none is planned. A laboratory's read patterns
are narrow and well known; GraphQL's cost here is an arbitrary query engine
sitting in front of patient data, which is a very large thing to have to
secure in exchange for saving a few round trips.

---

## 2. The rules

### R1 — Every endpoint declares who may call it

There is no implicit access. Authentication is enforced by
`apps.accounts.middleware.LoginRequiredMiddleware` for everything except an
explicit allow-list, and authorisation is declared per view.

An endpoint that omits a role check does not "default to open" — it fails
review.

### R2 — Patient data obeys the PHI barrier

Any endpoint that can return patient information must be reachable only by
roles permitted to see it. `apps.accounts.phi_barrier` blocks the installer
role by URL namespace. If you add an endpoint under a **new** namespace that
returns patient data, you must add that namespace to `CLINICAL_NAMESPACES` —
the barrier denies by namespace, and an unlisted new namespace is allowed by
default.

If your endpoint lives in an existing system namespace but returns patient
content, add its view name to `BARRED_VIEW_NAMES` instead.

The `rules` and `api` namespaces are both listed as clinical. Rule executions
record the patient facts a rule saw — an age, a sex, a diagnosis code and an
analyte value identify a person far more readily than most people expect.

### R3 — Reading patient data is logged

Disclosure of identifiable patient information is recorded for HIPAA
§164.528. Add your view to `PHI_VIEWS` in
`apps.compliance.middleware`, mapping the URL keyword to how it resolves to a
patient:

```python
PHI_VIEWS = {
    "yourapp:your_view": ("pk", "patient"),   # or ("pk", "order")
}
```

> This is keyed on **view name**, not URL path. An earlier version matched
> paths, and patient reports silently stopped being logged when the route
> moved. Do not reintroduce path matching.

### R4 — Writes are audited automatically; do not hand-roll logging

Model signals capture every create, update and delete in the Dx applications,
with field-level diffs and the acting user. You do not need to log anything.

Two things are deliberately excluded from automatic capture, because both are
already their own evidential record and both are high-volume:
`rules.RuleExecution` and `api.WebhookDelivery`. The *rules* that produce them
are audited, which is what an inspector asks about.

The other exception is **bulk operations**: `bulk_create`, `bulk_update` and
`QuerySet.update` emit no signals. If your endpoint uses them, either record a
summary event yourself with `apps.audit.recorder.record(...)` or wrap the block
in `suppress_auditing()` so the omission is deliberate and visible.

### R5 — An endpoint that authorises clinical work takes a signature

Anything that validates, verifies, releases or amends a result is an
electronic signature under 21 CFR Part 11 §11.200. It must re-authenticate the
caller, via `apps.compliance.services.apply_signature`.

A token alone is not a signature. A bearer token identifies a *service*; a
signature identifies a *person* at the moment of signing. This is why the v1
API can place orders and read results but cannot verify or release one: there
is no person on the other end of a client credential to sign.

The one exception is **autoverification**, where the signer is a decision rule
rather than a person. That is not a loophole in this rule — it is the rule
taken seriously. `ElectronicSignature.signer` is null and `automated_rule`
names the rule at the version that fired, so a report released this way says
"no human review" in its signature manifest. Recording a person who never
looked at the result would be false attribution, a graver finding than having
no human signature at all.

### R6 — Regulatory gates are enforced in the service layer, not the view

Call the services in `apps.laboratory.services` and
`apps.compliance.services`. They enforce competency, QC lockout and the
self-verification block. An endpoint that writes results by touching the ORM
directly bypasses every one of those controls.

### R7 — Service callers are attributed, not anonymous

A machine caller must set the audit context so its writes are attributable:

```python
from apps.audit.context import audit_as
from apps.audit.models import AuditSource

with audit_as(actor_username=f"instrument:{interface.name}",
              actor_role="instrument", source=AuditSource.INSTRUMENT):
    ...
```

Never attribute a service's writes to a human account.

### R8 — Errors are reported, never swallowed

An endpoint that silently drops what it cannot process is worse than one that
fails. Return the specific problem — which record, which field, why — and
persist the raw payload when the caller is a machine, as
`InstrumentMessage` does.

### R9 — Secrets are compared in constant time

Use `hmac.compare_digest` for tokens and shared secrets, never `==`.

### R10 — Anything leaving the system is encrypted

Exports, archives and backups are patient data outside the application's
controls. Use `apps.compliance.encryption` (AES-256-GCM). TLS in transit is
assumed and enforced by settings when `DEBUG` is off.

---

## 3. Authentication

### Session (people)

Browser endpoints use Django's session cookie. Cookies are `HttpOnly`,
`SameSite=Strict`, and `Secure` when `DEBUG` is off. CSRF protection applies to
every unsafe method.

### Client credentials (the v1 API)

`/api/v1/` uses a per-client credential, `<key id>.<secret>`, presented as a
bearer token. The key id is an indexed lookup; the secret is checked against a
password hash, so a leaked database gives an attacker nothing usable. An
unknown key id and a wrong secret are refused identically and take the same
time, so probing reveals nothing.

Each client carries its own scopes, rate limit, optional IP allow-list and
optional expiry, and can be disabled or rotated without disturbing any other.
Rotation takes effect immediately — there is no grace period, which is the
point of rotating.

### Shared bearer token (the laboratory's own middleware)

Service-to-service endpoints use a shared secret in the `Authorization`
header:

```http
POST /api/middleware/ingest/ HTTP/1.1
Authorization: Bearer <INSTRUMENT_INGEST_TOKEN>
Content-Type: application/json
```

Rules for token endpoints:

* Compare with `hmac.compare_digest`.
* Exempt from CSRF (`@csrf_exempt`) — a token-authenticated caller has no
  cookie to forge.
* Add the path to `PUBLIC_PATH_PATTERNS` in `apps.accounts.middleware`, since
  there is no session to authenticate.
* Never accept a token in the query string: URLs land in logs, proxies and
  browser history.
* Give each interface its own token where you can, so one can be revoked
  without disturbing the rest.

### What does not exist

No OAuth2, no per-user API keys, no JWT, no refresh tokens. A client credential
identifies a *system*, not a person, and there is no delegated-authority flow.
If an integration needs to act as a named person — to sign a verification, say —
it cannot: see R5.

---

## 4. Conventions

### URL shape

```
/api/<area>/<resource>/            collection
/api/<area>/<resource>/<id>/       single record
/interop/fhir/<Resource>/<id>/     FHIR, resource named as FHIR names it
```

Trailing slashes are required — Django's `APPEND_SLASH` will redirect, and a
redirected `POST` loses its body.

### Methods

| Method | Meaning |
| --- | --- |
| `GET` | Read. No side effects, ever — including no audit write beyond access logging. |
| `POST` | Create, or an action that is not idempotent. |
| `PUT`/`PATCH` | Update. |
| `DELETE` | Remove. Note that audit events, electronic signatures and several clinical records refuse deletion by design. |

### Identifiers

Records use string primary keys (UUID4 for new rows; some seeded rows use
readable ids). Treat them as opaque.

**Never expose a patient's primary key to a caller that may not see patient
data** — HIPAA Safe Harbor counts "any other unique identifying number" as an
identifier. `apps.audit.redaction.record_token` produces a keyed, stable,
non-reversible stand-in.

### Dates and times

ISO 8601, UTC, with an offset: `2026-09-15T14:30:00+00:00`. The database stores
timezone-aware values; never emit a naive one.

### Pagination

Every collection is paginated. An unbounded collection endpoint over patient
data is a data-exfiltration primitive, so there is no way to ask for all of it.

```
GET /api/v1/orders/?page=2&page_size=100
```

`page_size` defaults to 50 and is capped at 200. The body is:

```json
{
  "data": [ ... ],
  "page": {
    "number": 2, "size": 100, "total_pages": 7,
    "total_items": 683, "has_next": true
  }
}
```

A page beyond the end returns an empty `data` array, not a 404 — walking a
collection until it is empty must not require handling an error.

### Content types

`application/json` for JSON, `application/fhir+json` for FHIR when a client
asks for it, `text/plain` for HL7 v2.

---

## 5. Errors

Return the problem, not a generic failure.

```json
{
  "error": "Unknown test code",
  "detail": "No test definition matches 'GLUX'.",
  "field": "results[0].test_code"
}
```

| Status | Use for |
| --- | --- |
| `400` | Malformed request — unparsable JSON, missing field. |
| `401` | No credentials, or bad ones. |
| `403` | Authenticated, but not permitted. Includes a blocked regulatory control. |
| `404` | No such record — **also** used where confirming existence would itself disclose something. |
| `409` | Conflict, such as a failed audit chain verification. |
| `422` | Well-formed but not actionable — an unknown accession number, an unmatched test code. |
| `500` | A defect. Never use it for an expected condition. |

A refused regulatory control returns `403` with the reason and its citation:

```json
{
  "error": "The most recent QC run for GLU failed (1-3s). Investigate and repeat QC before releasing patient results.",
  "citation": "CLIA 42 CFR §493.1256(d)(3)"
}
```

Tell the caller *why*. "Forbidden" alone sends someone hunting for a bug that
is actually a control working correctly.

---

## 6. The v1 API

### Getting a credential

An administrator issues one at **Settings → API clients**. The token is shown
**once**, at creation, in the form `<key id>.<secret>`. It is stored as a
password hash; a system that can show you a credential again is a system that
stores it in a form an attacker can use.

```http
GET /api/v1/ HTTP/1.1
Authorization: Bearer 3f2a91c4de70b118.qKZ9p2vN-aXr…
```

`GET /api/v1/` is the discovery endpoint. It returns the server time, the
client's granted scopes and a map of every endpoint, so an integration can
check what it is allowed to do without guessing.

### Scopes

| Scope | Grants | Touches PHI |
| --- | --- | --- |
| `catalogue:read` | Test catalogue, LOINC, ICD-10 | No |
| `patients:read` | Patient demographics | Yes |
| `patients:write` | Register and update patients | Yes |
| `orders:read` | Orders and their diagnoses | Yes |
| `orders:write` | Place orders | Yes |
| `results:read` | Results | Yes |
| `reports:read` | Reports as JSON, FHIR or HL7 | Yes |
| `exceptions:read` | The exception queue | Yes |
| `webhooks:manage` | The client's own webhook subscriptions | No |

Grant the least that will do the job. HIPAA's minimum necessary standard
(45 CFR §164.502(b)) is not satisfied by "we gave them everything and trust
them", and a client holding a PHI scope is recorded as a recipient on every
read it performs.

### Rate limiting

A fixed window per client per minute, default 120, set per client. Exceeding it
returns `429` with `retry_after` in seconds. The purpose is to stop a looping
integration exhausting the database, not to meter usage.

### Endpoints

#### Catalogue — `catalogue:read`

| Endpoint | Notes |
| --- | --- |
| `GET /api/v1/tests/` | `?q=`, `?department=`, `?active=1` |
| `GET /api/v1/icd10/` | `?q=` matches code prefix or description; `?billable=1` |
| `GET /api/v1/loinc/` | `?q=` matches code prefix or long name |

#### Patients — `patients:read` / `patients:write`

| Endpoint | Notes |
| --- | --- |
| `GET /api/v1/patients/` | `?mrn=` exact, `?q=` name or MRN |
| `GET /api/v1/patients/<id>/` | |
| `POST /api/v1/patients/new/` | `mrn`, `first_name`, `last_name`, `date_of_birth` required |

Registering an MRN that already exists is **not an error**. It returns `200`
with `"created": false` and the existing record, so an integration retrying a
timed-out request cannot produce a duplicate patient.

`date_of_birth` is required because age drives reference intervals, critical
limits and several decision rules. A patient registered without one silently
degrades all three.

#### Orders — `orders:read` / `orders:write`

| Endpoint | Notes |
| --- | --- |
| `GET /api/v1/orders/` | `?status=`, `?patient=`, `?mrn=`, `?since=` (ISO 8601) |
| `GET /api/v1/orders/<id>/` | Includes results |
| `POST /api/v1/orders/new/` | |

```json
POST /api/v1/orders/new/
{
  "mrn": "MRN001",
  "tests": ["GLU", "HBA1C"],
  "priority": "STAT",
  "specimen_type": "Serum",
  "ordered_by": "Dr Jones",
  "diagnoses": [{"code": "E11.9", "type": "working"}]
}
```

The whole order is created or none of it is. An unknown test code or an unknown
ICD-10 code returns `422` and writes nothing — a partially-created order is
worse than no order, because somebody will draw blood for it.

#### Results and reports — `results:read` / `reports:read`

| Endpoint | Notes |
| --- | --- |
| `GET /api/v1/orders/<id>/results/` | `?verified_only=1` |
| `GET /api/v1/orders/<id>/report/` | `?format=json` (default), `fhir`, `hl7` |

A result carries `"autoverified": true` when it was released by a decision rule
rather than read by a person. Anything consuming results clinically should
surface that distinction.

#### Exception queue — `exceptions:read`

`GET /api/v1/exceptions/` — `?status=open` (default), `resolved`, `dismissed`,
`all`; `?source=`, `?severity=`.

#### Webhooks — `webhooks:manage`

| Endpoint | Notes |
| --- | --- |
| `GET /api/v1/webhooks/` | The calling client's own subscriptions only |
| `POST /api/v1/webhooks/new/` | Returns the signing secret, once |
| `GET /api/v1/webhooks/<id>/` | |
| `DELETE /api/v1/webhooks/<id>/` | |

---

## 7. Service endpoints

These authenticate with the shared `INSTRUMENT_INGEST_TOKEN` rather than a
client credential, because the caller is the laboratory's own middleware.

### `POST /api/middleware/ingest/`

Receives parsed instrument results.

```json
{
  "interface_id": "971dd681-e6fb-48dd-9e3a-a5e598e70dbe",
  "accession": "2026-09-15-0007",
  "instrument": "ARCH-1",
  "results": [
    {"test_code": "GLU", "value": "5.4", "units": "mmol/L", "flags": "N"}
  ]
}
```

| Response | Meaning |
| --- | --- |
| `200 {"applied": 4, "errors": []}` | All results written |
| `422 {"applied": 0, "errors": [...]}` | Nothing actionable |
| `400` | Unparsable JSON. The raw payload is still stored. |
| `401` | Missing or wrong token |

The raw payload is retained as an `InstrumentMessage` whatever happens,
`interface.test_code_map` translates the instrument's codes, writes are
attributed to `instrument:<name>`, and the full clinical and decision-rule
engines run exactly as they do for manual entry.

### `POST /api/middleware/query/` — host query

The other half of a bidirectional interface. An analyser reads a barcode and
asks what to run; the middleware translates its ASTM `Q` record or HL7
`QBP^Q11` into this call.

```json
{"specimen_id": "2026-09-15-0007", "interface_id": "971dd681-…"}
```

```json
{
  "specimen_id": "2026-09-15-0007",
  "status": "answered",
  "tests": ["GLU", "K"],
  "accession": "2026-09-15-0007",
  "detail": ""
}
```

| `status` | Meaning |
| --- | --- |
| `answered` | Tests are outstanding; run them |
| `no_work` | The order is complete, cancelled, or every test already has a result |
| `not_found` | No order, specimen or container matches the identifier |
| `refused` | The interface is configured unidirectional — `409` |

Notes worth knowing:

* The identifier is matched against the accession number first, then the
  specimen container id. An aliquot is itself a specimen, so a daughter tube's
  barcode resolves too.
* Test codes are returned **in the analyser's own vocabulary**, by inverting
  `interface.test_code_map`.
* Being asked about a specimen moves the order to *In Progress*. That is the
  earliest reliable signal a sample is in analysis, and more accurate than
  anyone remembering to press a button.
* Every query is recorded as a `HostQuery`, because "the analyser says it was
  never told to run that" is a real dispute.

### `POST /api/middleware/hl7/` — inbound orders and patient administration

The body is a raw HL7 v2 message. The response is always an HL7 ACK, because an
integration engine parses the ACK and will retry forever on anything else.

| Message | Effect |
| --- | --- |
| `ORM^O01`, `OML^O21` with `ORC-1 = NW` | Accession an order |
| `ORM^O01` with `ORC-1 = CA` | Cancel the order with that placer number |
| `ADT^A01/A04/A05/A08/A28/A31` | Register or update a patient |
| `ADT^A40` | Merge one MRN into another |

| ACK | HTTP | Meaning |
| --- | --- | --- |
| `AA` | 200 | Accepted and applied |
| `AE` | 422 | Understood and refused — do not retry unchanged |
| `AR` | 400 | Could not be parsed |

`AE` and `AR` are kept distinct deliberately. A sender that gets `AE` knows the
message is wrong; one that gets `AR` knows it is malformed. Conflating them is
why integration failures take days to diagnose.

Behaviour worth knowing:

* Identity is the **MRN and nothing else**. Matching on name and date of birth
  would merge two different people who share both, which happens more often
  than intuition suggests and is unrecoverable once results are attached.
* A retransmitted order with a placer number that already exists returns
  `"action": "duplicate"` rather than accessioning a second specimen.
* A merge repoints orders onto the surviving record and **retains** the old
  one, flagged as merged. Deleting it would break the audit trail's references.
* `DG1` segments become ICD-10 diagnoses on the order. A code absent from the
  local catalogue is still recorded — the hospital's coding is the record, even
  when our table lags it.
* A refused message raises an item on the exception queue, so a rejection is
  seen by a person rather than living in an integration log.

### `GET /interop/fhir/DiagnosticReport/<order>/`

FHIR R4 `DiagnosticReport`. `?bundle=1` for a self-contained `Bundle` with the
`Patient` and every `Observation`. Session authenticated; logged as a PHI
disclosure.

### `GET /interop/hl7/oru/<order>/`

HL7 v2.5 `ORU^R01` as `text/plain`. Session authenticated; logged as a PHI
disclosure.

### `GET /audit/api/verify/`

Verifies the audit hash chain. Managers and the installer.

```json
{"ok": true, "checked": 1284, "head_sequence": 1284, "head_hash": "5369…", "problems": []}
```

Returns `409` when the chain fails, so a monitor can alert on status alone.

### `GET /healthz/`

Unauthenticated liveness probe. Deliberately reveals nothing beyond liveness
and audit-recorder health.

---

## 8. Webhooks

A subscription is created through the API (`webhooks:manage`) or at
**Settings → Webhooks**. Each delivery is an HTTP `POST` of:

```json
{
  "id": "1f0c…",
  "event": "result.verified",
  "created_at": "2026-09-15T14:30:00+00:00",
  "data": { ... }
}
```

### Events

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

### Verifying a delivery

```
X-Dx-Event: result.verified
X-Dx-Delivery: 1f0c…
X-Dx-Signature: t=1789567800,v1=6c3f…
```

`v1` is `HMAC-SHA256(secret, "<t>." + raw body)`, hex encoded. Recompute it over
the **raw** bytes, compare in constant time, and reject anything whose `t` is
more than five minutes old. A captured payload is then useless to replay.

The reference implementation is `apps.api.webhooks.verify`, which is the same
function the tests exercise:

```python
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

### What a payload contains

**Direct identifiers are stripped by default.** A patient's surrogate id
survives; the MRN, name, date of birth and contact details are replaced with
`[redacted]`. A subscriber entitled to the detail fetches it over the API,
where the read is authenticated, scoped and recorded as a disclosure — a
webhook body, by contrast, lands in somebody's application log.

A subscription may set `include_identifiers` where the receiving system is
itself a covered entity and the disclosure is accounted for. That is a decision
somebody has to make deliberately, which is why it is off by default.

### Delivery guarantees

* **Fired after commit.** A rolled-back transaction never emits an event
  claiming something happened.
* **Retried with backoff** — roughly 30s, 2m, 8m, 30m, 2h — up to six attempts.
* **HTTPS only.** An `http://` subscription is refused at creation.
* **A persistently failing subscriber is disabled** after twenty consecutive
  failures, and raises an exception queue item so somebody is told. An
  integration that quietly stopped working is how a ward finds out about a
  critical result by telephone three days later.

Delivery is performed by a worker, so a slow subscriber cannot stall result
entry:

```bash
python manage.py deliver_webhooks --forever --interval 15
```

---

## 9. Adding an endpoint: checklist

- [ ] Roles declared explicitly (R1)
- [ ] If it returns patient data: namespace listed in `CLINICAL_NAMESPACES`, or
      view listed in `BARRED_VIEW_NAMES` (R2)
- [ ] If it returns patient data: view registered in `PHI_VIEWS` (R3)
- [ ] Bulk writes record their own summary event, or are explicitly suppressed (R4)
- [ ] Anything that authorises clinical work calls `apply_signature` (R5)
- [ ] Writes go through the service layer, not the ORM directly (R6)
- [ ] Machine callers set the audit context (R7)
- [ ] Failures are reported with specifics, and raw payloads retained (R8)
- [ ] Secrets compared with `hmac.compare_digest` (R9)
- [ ] Anything written to a file is encrypted (R10)
- [ ] Tests cover: permitted role succeeds, barred role is refused, a blocked
      control returns `403` with its reason, and a malformed payload is
      reported rather than swallowed
- [ ] `manage.py test tests` passes
- [ ] This document updated
