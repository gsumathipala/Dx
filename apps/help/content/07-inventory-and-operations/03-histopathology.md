---
title: Histopathology
summary: Tracking blocks and slides through the histology workflow.
audience: scientist, manager
keywords: histology, histopathology, block, slide, stain, cassette, embedding
---

## The workflow

Histopathology differs from clinical chemistry: the product is a **slide** a
pathologist examines, and the process is a sequence of physical
transformations, each of which can be tracked.

```
  Specimen → Grossing → Processing → Embedding → Sectioning → Staining → Reading
              (cassette)  (dehydrate)  (block)     (slide)     (H&E etc)
```

## Blocks

A **block** is tissue embedded in paraffin, ready for sectioning. Each has a
unique id, conventionally the accession number with a letter suffix —
`2026-09-15-0001-A`, `-B` — so multiple blocks from one specimen stay
distinguishable.

| Status | Stage |
| --- | --- |
| Cassette printed | Labelled, awaiting grossing |
| Grossed | Tissue selected and placed |
| Processed | Dehydrated and infiltrated |
| Embedded | Set in paraffin |
| Sectioned | Cut |
| Archived | In long-term storage |

Record who grossed a block and where it is archived. Blocks are retained for
years and are sometimes the only remaining material — they may be recut for
further stains long after the original report.

## Slides

A **slide** is a section on glass, stained. Each records its block, its stain,
and its status through printed → stained → cover-slipped → released →
archived.

### Stains

| Stain | Shows |
| --- | --- |
| **H&E** | Haematoxylin and eosin — the routine stain; nuclei blue, cytoplasm pink |
| **PAS** | Periodic acid–Schiff — glycogen, basement membranes, fungi |
| **Special stains** | Connective tissue, organisms, pigments |
| **Immunohistochemistry** | Specific proteins, by antibody — the basis of most tumour classification |

## Why tracking matters here

Histology is a manual, multi-step process on material that is often
irreplaceable. A block cut from the wrong specimen produces a diagnosis for the
wrong patient, and unlike a chemistry result there is rarely a second sample.

Tracking every transformation means you can always answer: which specimen did
this slide come from, who handled it, and what remains.

## Retention

Blocks and slides are retained far longer than most specimens, because a case
may be reviewed years later — for a second opinion, for staging, or in
litigation. See [record retention](/help/administration/record-retention/) for
the periods.
