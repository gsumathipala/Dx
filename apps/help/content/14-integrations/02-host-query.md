---
title: Host query — analysers that ask
summary: Bidirectional instrument interfacing: the analyser reads a barcode and asks what to run.
audience: scientist, manager
keywords: host query, bidirectional, ASTM Q record, QBP, worklist, analyser, tutorial
---

## The two halves of an interface

Most laboratories have the easy half: the analyser produces results and sends
them to the LIS. That is a **unidirectional** interface.

The other half is the analyser asking the LIS what to run. Without it you have
two options, both bad:

1. **Run everything the analyser offers on every sample.** Wasteful, and it
   consumes reagent that then cannot be used on a request that needed it.
2. **Key the request into the analyser by hand.** Which is the transcription
   error the interface existed to remove.

**Host query** is the second half. The analyser reads the tube's barcode, asks
the LIS, and runs exactly what is ordered.

## How it works

1. The analyser sends a query — an ASTM `Q` record, or an HL7 `QBP^Q11`.
2. The instrument server translates it and asks the LIS.
3. The LIS answers with the outstanding test codes for that specimen.
4. The instrument server replies to the analyser in its own dialect.

Every exchange is recorded, because "the analyser says it was never told to run
that" is a real dispute and the answer has to exist somewhere other than a log
that rotated last week.

## What the LIS will and will not answer

**Only tests with no result yet.** A test that already has a value is not
returned. An analyser re-running a verified result would silently overwrite a
report somebody has already acted on.

**Only for an open order.** A completed or cancelled order returns *no work*,
which the analyser reads as "park this sample" — not as an error.

**In the analyser's own codes.** If the interface has a code map, it is
inverted for the answer. An analyser cannot be expected to know what a Dx test
code means.

**Never on a unidirectional interface.** The request is refused outright.
Handing a work list to an analyser the laboratory has not configured to receive
one would make it run tests nobody ordered.

## A useful side effect

Being asked about a specimen means it reached the analyser. That is the
earliest reliable signal a sample is actually in analysis, so the order moves
to **In Progress** automatically — more accurate than anyone remembering to
press a button.

## Tutorial: turn it on for one analyser

### 1. Configure the interface in Dx

**Settings → Instrument interfaces →** your analyser.

Set **Direction** to *Bidirectional (orders and results)*.

Check the **test code map** is populated. It maps the instrument's codes to
yours, and is inverted to answer queries. An empty map means the analyser is
answered with Dx codes, which it will probably not understand.

### 2. Restart the instrument server with host query enabled

```bash
dx-instrument-server \
  --protocol astm \
  --port 5150 \
  --interface-id <the interface id> \
  --host-query
```

The startup line confirms it: `Listening on 0.0.0.0:5150 (ASTM) → … [host query
enabled]`.

Host query is **opt-in on both sides** — the interface record and the listener.
Either one off and queries are refused.

### 3. Configure the analyser

On the analyser, set the host communication mode to query the host for each
sample. The wording varies: *host query*, *query host*, *LIS query*, *download
worklist*.

### 4. Watch the log

**Settings → Host query log** shows every question and answer: which interface,
which specimen, the outcome, how many tests were returned and how long it took.

| Status | Meaning |
| --- | --- |
| Answered | Tests were outstanding; the analyser was told |
| No work | The order is complete, cancelled, or every test has a result |
| No matching specimen | Nothing matched that barcode |
| Refused | The interface is configured unidirectional |

## Barcodes that do not match

The identifier is tried against the accession number first, then the specimen's
container id. An aliquot is itself a specimen, so a daughter tube's barcode
resolves through the same lookup.

If you see *No matching specimen* repeatedly, compare what the analyser reads
with what is printed on the tube — most often the analyser is stripping a
prefix or a check digit.

## What the installer sees

The host query log, redacted. The interface, the time, the outcome and the
latency are visible; the specimen identifier and the tests returned are not.
A barcode resolves to a person, and a list of ordered tests is a clinical
statement about them.
