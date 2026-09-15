---
title: Instrument interfaces
summary: Connecting an analyser, mapping its codes, and diagnosing a silent interface.
audience: scientist, manager, administrator
keywords: interface, analyser, astm, hl7, mllp, middleware, instrument, mapping
---

## How the connection works

```
  Analyser ──TCP──▶ Instrument server ──HTTPS──▶ Dx
             ASTM     parses, validates          applies results,
             or HL7   frames and checksums       runs clinical rules
```

The **instrument server** is a separate process, deliberately. It can run on a
workstation beside the analyser, needs only the Python standard library, and
keeps raw protocol handling out of the application.

## Configuring an interface

**Settings → Instrument interfaces**: name, linked equipment, protocol,
direction, host and port, and a **test code map**.

### The test code map

Analysers use their own codes. The map translates them:

```json
{"0001": "GLU", "0002": "NA", "0017": "CREA"}
```

Without a mapping, a code Dx does not recognise is reported as an error rather
than guessed at — a wrong mapping would attach one analyte's value to another
analyte's name, which is the worst possible failure.

### Direction

**Unidirectional** — results only. The analyser sends what it has run.

**Bidirectional** — the analyser queries the LIS for the worklist for a
barcode, then returns results. Also called host query mode.

> Bidirectional operation is **not yet implemented**. The field exists; the
> query side does not.

## Running the instrument server

```bash
cd instrument_server
INSTRUMENT_INGEST_TOKEN=... python -m dx_instrument.cli --port 5150 --protocol astm
```

Test it without an analyser:

```bash
python -m dx_instrument.simulator 2026-09-15-0007 --protocol astm
```

## What happens to a message

1. **Framing and checksum** are verified. A frame failing its checksum is
   answered with NAK so the analyser retransmits — a corrupted result is never
   forwarded.
2. **Parsed** into a common shape.
3. **Posted** to Dx with a bearer token.
4. **Stored raw**, whatever happens, as an instrument message.
5. **Applied** to the matching order, running the full clinical engine — delta
   checks, critical values, reflex rules, notifiable conditions.

Results are attributed to `instrument:<name>`, never to a person.

## Nothing is dropped

If Dx is unreachable, the payload is written to a spool file and retried. A
rejection is spooled too, so it can be inspected rather than lost.

## Diagnosing a quiet interface

**Settings → Instrument messages** shows raw traffic with status and any error.
An enabled interface with no traffic for over an hour is flagged **stale**.

| Symptom | Likely cause |
| --- | --- |
| No messages at all | Network, wrong port, analyser not configured to send |
| Messages, status Failed | Unknown accession — the order does not exist in Dx |
| Messages, unknown test code | Missing entry in the test code map |
| Checksum failures | Cable, serial settings, converter |
| Results applied to nothing | Accession mismatch between analyser and LIS |

The commonest cause by far is an **accession number mismatch**: the analyser
reads a barcode the LIS never issued, or reads it with a prefix.

> Because the raw payload is always retained, you can see exactly what the
> analyser sent rather than inferring it. Start there.

## A note on the message log

Instrument payloads contain patient identifiers in their `PID` segment. The
message log therefore hides payloads from roles barred from patient data — an
installer sees the interface, status, parse outcome and error, which is what
diagnosis needs.
