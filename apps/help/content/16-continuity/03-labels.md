---
title: Specimen labels
summary: Printing labels, what is on them, and why you check against the wristband.
audience: clerk, phlebotomist, scientist
keywords: label, barcode, print, ZPL, wristband, patient identification, tutorial
---

## What is on a label

| On the label | Why |
| --- | --- |
| Patient name | The largest thing on it, because it is what you check against the wristband |
| MRN and date of birth | The second and third identifiers |
| Accession number, as text and barcode | Identifies the **specimen** |
| Specimen type and collection time | So the right tube is drawn and the clock is right |
| STAT / Urgent, reversed out | Legible across a bench at a glance |

The Joint Commission's National Patient Safety Goal 01.01.01 requires **two
patient identifiers** before collecting a specimen. The accession number is not
one of them — it identifies the tube, not the person.

**Nothing is abbreviated to fit.** A label that dropped half a surname to fit
the width is how two patients called Smith become one.

## Printing

From an order: **Labels**.

| What you want | How |
| --- | --- |
| A printable sheet on any printer | Just open it and press Print |
| Raw ZPL for a thermal printer | Add `?format=zpl` |
| Several per specimen, for aliquots | Add `?copies=3` (up to 10) |

## Before you draw

**Check the label against the patient's wristband, with the patient, at the
bedside.** Ask them to say their name and date of birth rather than reading it
to them — a patient who is unwell, deaf or simply being polite will agree to
the wrong name.

Label the tube **at the bedside, after drawing**, never in advance. Pre-labelled
tubes are the single largest cause of wrong-blood-in-tube, and a wrong-blood-in-
tube in transfusion can kill somebody.

## Reprinting

Unrestricted, and recorded.

That is a deliberate choice. A laboratory that cannot reprint a label will
hand-write one, and a hand-written tube is exactly the error the barcode
existed to remove. So the control is the audit record, not a refusal.

## If a barcode will not scan

1. Check the label is not creased around the tube — a barcode bent around a
   small diameter reads intermittently.
2. Check nothing is covering the clear space either side. That margin is part
   of the symbol, not decoration.
3. Reprint rather than keying by hand.

The barcode is Code 128, which every laboratory scanner reads. The number is
printed underneath so a scanner failure still leaves something a person can
type.
