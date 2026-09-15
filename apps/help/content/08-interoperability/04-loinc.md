---
title: LOINC coding
summary: What a LOINC code specifies, why local codes are not enough, and how to choose one.
audience: scientist, manager
keywords: loinc, coding, terminology, standard, mapping
---

## What LOINC is

Logical Observation Identifiers Names and Codes: a universal code for
*what was measured*. Maintained by the Regenstrief Institute and free to use.

## The six axes

A LOINC code specifies six things, and the precision is the point:

| Axis | Example | Distinguishes |
| --- | --- | --- |
| **Component** | Glucose | What substance |
| **Property** | Mass concentration | What quantity |
| **Time aspect** | Point in time | Instant or timed collection |
| **System** | Serum/plasma | Which specimen |
| **Scale** | Quantitative | Number, ordinal, nominal, narrative |
| **Method** | (often unspecified) | Where method changes meaning |

So `2345-7` is *glucose, mass concentration, point in time, serum or plasma,
quantitative* — and is a different code from glucose in cerebrospinal fluid,
from a 2-hour post-load glucose, and from a urine glucose dipstick.

## Why local codes are not enough

Your `GLU` means whatever your laboratory decided. Another laboratory's `GLU`
may be a different specimen or a different timing. A receiving system storing
both has two incompatible things under one heading.

Reference intervals differ between them. Clinical meaning differs. Trending them
together is actively misleading.

LOINC removes the ambiguity because the code itself carries the distinctions.

## Choosing a code

**Settings → LOINC catalogue** holds codes with their long and short names,
component, property, time aspect, system, scale and method.

Set a test's `loinc_code` on its test definition.

When choosing:

1. **Match the specimen.** Serum/plasma and urine are different codes.
2. **Match the property.** Mass concentration and substance concentration are
   different — this corresponds to mg/dL versus mmol/L.
3. **Match the timing.** Random, fasting and timed collections differ.
4. **Only specify method where it matters.** Most codes leave method
   unspecified; specify it where the method changes interpretation, as for some
   immunoassays.

The Regenstrief **RELMA** tool exists for exactly this mapping work and is worth
using for a full catalogue.

## Getting it wrong

A wrong LOINC code is worse than none. A receiving system trusts the code: if
you send a urine glucose coded as serum glucose, it is filed and trended as
serum glucose, and the error is invisible at the far end.

If you are unsure, leave it unmapped and send the local code rather than
guessing.
