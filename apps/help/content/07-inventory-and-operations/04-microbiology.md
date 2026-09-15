---
title: Microbiology
summary: Cultures, susceptibility testing, cascade reporting and the antibiogram.
audience: scientist, medic, manager
keywords: microbiology, culture, susceptibility, ast, mic, clsi, eucast, antibiogram, resistance
---

## How microbiology differs

Most laboratory tests produce a number within hours. A culture produces a
sequence of provisional answers over days, and the final answer is a name and a
susceptibility profile rather than a value.

```
  Setup → Incubation → Reading → Identification → Susceptibility → Final
   day 0    18–24 h+    growth?     organism         S / I / R      report
```

Provisional results matter clinically: a Gram stain available at four hours
guides empirical therapy long before the final report.

## Cultures

A culture records its order, specimen, incubator location, setup time and
status, with a **preliminary** result (Gram stain, early morphology) and a
**final** result (identification and susceptibility).

Incubation time is shown, because time matters: a blood culture negative at
24 hours is not negative, it is incomplete.

## Susceptibility testing

Each organism–antibiotic pair records a result:

| Interpretation | Meaning |
| --- | --- |
| **S** — Susceptible | Likely to respond at standard dosing |
| **I** — Intermediate / susceptible-dose-dependent | May respond at higher dose, or where the drug concentrates |
| **R** — Resistant | Unlikely to respond |

These are **not** direct measurements. They are interpretations of a measured
MIC or zone diameter against published **breakpoints**, which encode the drug's
pharmacokinetics and clinical outcome data as well as the organism's biology.

### MIC and zone diameter

**MIC** — minimum inhibitory concentration, in mg/L. The lowest concentration
preventing visible growth.

**Zone diameter** — in millimetres, from disc diffusion. Larger means more
susceptible.

### CLSI and EUCAST

Two major breakpoint systems, and they do not always agree. A given MIC can be
susceptible under one and resistant under the other, because they weigh dosing
regimens and outcome data differently.

Record which standard was used. A susceptibility result without its standard is
not interpretable.

Breakpoints are revised as resistance evolves and dosing changes. Using last
decade's breakpoints can report an organism as susceptible to a drug that will
fail.

## Cascade reporting

Not every tested antibiotic is reported. **Cascade** or selective reporting
releases a first-line panel, and reports broader-spectrum agents only where the
first line is resistant.

The reasoning is antimicrobial stewardship: clinicians prescribe what they see.
Reporting a broad-spectrum agent on an organism susceptible to narrow-spectrum
treatment drives unnecessary broad prescribing, which drives resistance.

Dx supports this with a **reported** flag and a tier on each antibiotic — a
result can be recorded without being released.

## The antibiogram

An antibiogram summarises local susceptibility: the percentage of each organism
susceptible to each agent, over a period.

It matters because empirical therapy — treatment before the culture is back —
should reflect **local** resistance. If 30% of local *E. coli* are resistant to
a first-line agent, that agent is a poor empirical choice regardless of national
guidance.

Recording susceptibilities relationally, rather than as free text, is what makes
an antibiogram possible.
