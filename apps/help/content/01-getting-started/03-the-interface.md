---
title: Finding your way around
summary: The sidebar, the search box, the dashboard, and keyboard shortcuts.
audience: everyone
keywords: navigation, sidebar, search, dashboard, barcode, keyboard, shortcuts
---

## The shape of the screen

Every screen has the same three parts:

- **The sidebar** on the left: search, then the screens you use during a shift,
  then oversight screens, then your account.
- **The title bar**: where you are, and the actions available here.
- **The content area**: the work itself.

## The search box

At the top of the sidebar. It is the fastest way to reach anything, and it
takes three kinds of input:

| You type | You get |
| --- | --- |
| An accession number (`2026-09-15-0007`) | That order, opened where it currently sits |
| An MRN (`MRN-100001`) | That patient's record |
| A surname | A list of matching patients and orders |

An **exact** accession number or MRN does not show you a list of one — it takes
you straight there.

### It opens the order where the work is

An order in different states needs different screens, so search sends you to
the right one:

| The order is | You land on |
| --- | --- |
| Awaiting reception | Specimen receiving |
| Awaiting results or authorisation | Result entry |
| Released | The report |

### Barcode scanners work with no setup

A handheld scanner types the barcode and presses Enter — exactly as if you had
typed it. Click into the search box, scan the tube, and you are on that order.

Press **`/`** from anywhere to jump into the search box without the mouse.

## The sidebar

The sidebar carries only what you use during a shift. It changes with your
role: a phlebotomist sees six entries, an administrator seventeen.

Everything configured occasionally — the test catalogue, clinical rules, QC
targets, retention schedules — lives behind **Settings**, which is a
*searchable index* rather than a long list. Type `delta`, `calibration` or
`retention` instead of scanning for it.

## The dashboard

Your dashboard is a worklist, not a report. It shows what needs you now:

- **Critical values** awaiting clinician notification, with how long each has
  been waiting
- **STAT orders** still open, with elapsed time
- **The queues you can clear** — awaiting results, awaiting technical
  validation, awaiting clinical verification
- **Reagents** at or below their threshold

Every row is clickable and goes straight to the action. Counts and averages sit
below the work, not above it.

## Keyboard shortcuts

| Key | Where | Does |
| --- | --- | --- |
| `/` | Anywhere | Jump to the search box |
| `Enter` or `↓` | Result entry | Move to the next value |
| `↑` | Result entry | Move to the previous value |
| `Ctrl` + `Enter` | Result entry | Save |

In result entry, **Enter moves down rather than submitting the form**. Entering
a twenty-analyte panel should not need the mouse at all, and lab staff often
have one hand on a rack.

## Reading the screen

Status badges use consistent colours throughout:

| Colour | Meaning |
| --- | --- |
| Green | Complete, passed, acceptable, active |
| Amber | In progress, warning, approaching a limit |
| Red | Failed, rejected, breached, critical |
| Grey | Draft, scheduled, not applicable |

## Printing

Reports are laid out for paper: use your browser's print command, or the
**Print** button. The sidebar and buttons are omitted automatically.
