---
title: Writing a rule
summary: A walkthrough — conditions, groups, actions, and the facts you can condition on.
audience: scientist, manager
keywords: tutorial, rule builder, conditions, actions, groups, facts
---

## Tutorial: suppress a haemolysed potassium

We will build the rule most laboratories want first.

**The clinical problem.** Potassium leaks out of red cells. A haemolysed
specimen gives a potassium that is real as a measurement and wrong as a
clinical fact. Reporting it without comment invites somebody to treat a
hyperkalaemia the patient does not have.

### 1. Open the builder

**Settings → Decision rules → New**.

### 2. Describe the rule

| Field | Value |
| --- | --- |
| Name | `Haemolysis — potassium suppression note` |
| Description | `Potassium is falsely raised by in-vitro haemolysis. Warn the requester rather than reporting the number alone.` |
| Trigger | A result is entered or corrected |
| Applies to | `K` — Potassium |
| Priority | `50` |

**Priority** decides evaluation order — lower first. Leave it at the default
unless you have a reason.

### 3. Add the conditions

Two conditions, both in **group 0**, so both must hold:

| Subject | Operator | Value |
| --- | --- | --- |
| Result — numeric value | is greater than | `5.5` |
| Specimen — condition at reception | is | `Marginal` |

### 4. Add the action

| Kind | Text |
| --- | --- |
| Append an interpretive comment | `Potassium may be falsely elevated: specimen recorded as haemolysed at reception. Suggest repeat on a fresh sample if clinically unexpected.` |

### 5. Save

It saves as a **draft** and does not fire. Go and
[try it and approve it](/help/rules-and-automation/approving-a-rule/).

---

## Groups: AND and OR

Conditions in the **same group** must *all* hold. **Any group** matching is
enough.

So this:

| Group | Condition |
| --- | --- |
| 0 | Result value > 5.5 |
| 0 | Specimen condition is Marginal |
| 1 | Result value > 7.0 |

means *(value above 5.5 **and** haemolysed) **or** (value above 7.0)*.

That is enough for everything a laboratory has actually asked for. If you find
yourself wanting parentheses, you probably want two rules.

## The facts you can condition on

| Fact | Notes |
| --- | --- |
| Result — numeric value | Blank for a non-numeric result |
| Result — text value | The raw string, for qualitative results |
| Result — flag | Normal / Low / High / Critical Low / Critical High |
| Result — position vs reference interval | `below`, `within`, `above`, `unknown` — uses the patient's demographic interval where one exists |
| Result — is a critical value | |
| Result — triggered a delta check | |
| Test — code, department | |
| Patient — age in years, age in days | Days matters in neonatology |
| Patient — sex | |
| Order — priority | Routine / Urgent / STAT |
| Order — ICD-10 diagnosis codes | A list; `is one of` tests membership |
| Specimen — type, condition at reception | |
| Previous result — value, days ago | The patient's own last numeric result for this test |
| Change from previous — percent, absolute | |
| Quality control — status for this test | `in-control`, `out-of-control` |
| Entry — source | `manual` or `instrument` |

### A fact that is unavailable never matches

If a patient has no previous result, `Previous result — value is less than 5`
is **false**, not true. A rule must not fire because something could not be
measured. Silence is not evidence of normality.

The one exception is `is blank`, which is how you deliberately test for
absence — "this is the patient's first ever result for this analyte".

## The actions

| Action | What it does |
| --- | --- |
| Append an interpretive comment | Adds text to the result's comments, attributed as `[Rule name] …` |
| Add a result flag | Any label you like — `Review`, `Repeat`, `Senior` |
| Add a follow-on test to the order | Reflex testing |
| Request automatic verification | See [autoverification](/help/rules-and-automation/autoverification/) |
| Hold the result from release | Forces a person to look |
| Raise an item on the exception queue | With a severity |
| Send an internal message | To everyone holding a role |

Actions run in order. A comment is not added twice if the rule fires again on
the same result.

## Stop on match

Tick **stop on match** and no later rule is evaluated for that result. Use it
sparingly: it is the source of "why didn't my rule fire?" in every rules engine
ever built. Check the priority ordering before reaching for it.

## A rule with no conditions

…matches every result it is evaluated against. The builder warns you, because
it is occasionally what you want (a standard footnote on every microbiology
report) and usually is not.
