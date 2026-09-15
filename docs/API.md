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
6. [Endpoints that exist today](#6-endpoints-that-exist-today)
7. [Webhooks](#7-webhooks)
8. [Adding an endpoint: checklist](#8-adding-an-endpoint-checklist)

---

## 1. Status of the API

Dx is a server-rendered application. It is **not** API-first, and there is no
general REST or GraphQL surface yet.

What exists today is a small set of purpose-built endpoints:

| Purpose | Style |
| --- | --- |
| Instrument result ingest | JSON over HTTPS, bearer token |
| FHIR R4 export | JSON, session authenticated |
| HL7 v2 export | Plain text, session authenticated |
| Audit chain verification | JSON, session authenticated |
| Health probe | JSON, unauthenticated |

A general API is planned. Until it lands, these rules govern anything added.

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

The exception is **bulk operations**: `bulk_create`, `bulk_update` and
`QuerySet.update` emit no signals. If your endpoint uses them, either record a
summary event yourself with `apps.audit.recorder.record(...)` or wrap the block
in `suppress_auditing()` so the omission is deliberate and visible.

### R5 — An endpoint that authorises clinical work takes a signature

Anything that validates, verifies, releases or amends a result is an
electronic signature under 21 CFR Part 11 §11.200. It must re-authenticate the
caller, via `apps.compliance.services.apply_signature`.

A token alone is not a signature. A bearer token identifies a *service*; a
signature identifies a *person* at the moment of signing.

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

### Bearer token (services)

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

No OAuth2, no API keys per user, no JWT. Do not assume them.

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

Not yet standardised, because no collection endpoint exists. When one is added:
`?limit=` and `?offset=`, a `count` in the body, and a default limit — an
unbounded collection endpoint over patient data is a data-exfiltration
primitive.

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

## 6. Endpoints that exist today

### `POST /api/middleware/ingest/`

Receives parsed instrument results. **Bearer token.**

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
| `422 {"applied": 0, "errors": [...]}` | Nothing actionable — unknown accession, unmapped test code |
| `400` | Unparsable JSON. The raw payload is still stored. |
| `401` | Missing or wrong token |

Behaviour worth knowing:

* The raw payload is retained as an `InstrumentMessage` whatever happens, so a
  disputed result can be traced to what the analyser actually sent.
* `interface.test_code_map` translates the instrument's codes to Dx test codes.
* Results are written under the interface's identity
  (`instrument:<name>`), never a person's.
* The full clinical engine runs: delta checks, critical values, reflex rules
  and notifiable conditions.

### `GET /interop/fhir/DiagnosticReport/<order>/`

FHIR R4 `DiagnosticReport`. Add `?bundle=1` for a self-contained `Bundle` with
the `Patient` and every `Observation`. Session authenticated; logged as a PHI
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

Unauthenticated liveness probe.

```json
{"status": "ok", "audit_recorder": "running", "audit_queue_depth": 0}
```

Deliberately reveals nothing beyond liveness and audit-recorder health.

---

## 7. Webhooks

**Not implemented.** When they are, these rules apply:

* **Signed.** HMAC-SHA256 of the body with a per-subscription secret, in
  `X-Dx-Signature`. Receivers must compare in constant time.
* **Replay-resistant.** Include a timestamp in the signed material and reject
  anything stale.
* **No patient data in the payload.** Send an event type and a record
  reference; the receiver fetches the detail over an authenticated endpoint
  that logs the disclosure. A webhook body lands in logs and queues you do not
  control.
* **Retried with backoff, and spooled.** Never dropped silently.
* **Fired after commit**, never from inside the transaction — a rolled-back
  transaction must not emit an event that claims something happened.

Planned events: `order.created`, `result.entered`, `result.verified`,
`report.released`, `report.amended`, `critical_value.raised`, `qc.failed`.

---

## 8. Adding an endpoint: checklist

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
