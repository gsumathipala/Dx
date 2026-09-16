# Deferred work, broken down

Everything Dx deliberately does not do, as work items.

This is the companion to the "What this system does *not* do" section of
[REGULATORY.md](REGULATORY.md). That section says *what* is absent and why;
this one says what it would take to close each gap.

Nothing here is committed to. It exists so that a decision to start one of
these is made with the shape of the work visible, rather than discovered three
weeks in.

**On the sizes.** Indicative, for one or two experienced developers with a
domain expert available, and excluding validation and deployment. They are
there to separate *a fortnight* from *a quarter* from *a different product* —
not to be planned against.

**On the decision points.** Each item lists the questions that must be answered
by somebody other than a developer. Starting an item before its decisions are
made is the main way these go wrong.

---

## Contents

**Do these first** — cheap, high value, mostly unblocked
1. [Colour-independent result flags](#1-colour-independent-result-flags)
2. [Positive patient identification at collection](#2-positive-patient-identification-at-collection)
3. [Send-outs and reference laboratory management](#3-send-outs-and-reference-laboratory-management)
4. [High availability and disaster recovery](#4-high-availability-and-disaster-recovery)

**Substantial, self-contained**
5. [Advanced quality control](#5-advanced-quality-control)
6. [Accessibility to WCAG 2.1 AA](#6-accessibility-to-wcag-21-aa)
7. [Point-of-care testing](#7-point-of-care-testing)
8. [Business intelligence and de-identified extracts](#8-business-intelligence-and-de-identified-extracts)
9. [Electronic laboratory reporting to public health](#9-electronic-laboratory-reporting-to-public-health)
10. [Internationalisation](#10-internationalisation)

**Architectural — decide what Dx is first**
11. [Multi-site and multi-tenancy](#11-multi-site-and-multi-tenancy)

**Separate products in all but name**
12. [Anatomic pathology depth](#12-anatomic-pathology-depth)
13. [Blood bank and transfusion medicine](#13-blood-bank-and-transfusion-medicine)
14. [Molecular and next-generation sequencing](#14-molecular-and-next-generation-sequencing)
15. [Revenue cycle](#15-revenue-cycle)
16. [Patient portal](#16-patient-portal)

**Ongoing**
17. [Validation and product maturity](#17-validation-and-product-maturity)

---

# Do these first

## 1. Colour-independent result flags

**Size: days.** This is on the list because it is a patient-safety defect, not
because it is an accessibility nicety.

Result flags are conveyed by colour. WCAG 1.4.1 prohibits colour as the only
means of conveying information, and the clinical reason is the same as the
accessibility one: around one in twelve men has a colour vision deficiency, and
one of them will be the person reading a critical flag at three in the morning.

1. Audit every place a flag, status or severity is shown by colour alone —
   result rows, the worklist, the exception queue, QC charts, delta flags.
2. Add a non-colour signal to each: a glyph, a letter code (`H`, `L`, `↑↑`),
   or text. The printed report already carries text; the screen should match it.
3. Check contrast ratios for every foreground/background pair against 4.5:1.
4. Verify with a deuteranopia/protanopia simulator on the result entry screen
   and the exception queue specifically.
5. Add a regression test asserting that flag rendering emits a text token, not
   only a CSS class.

**Decisions:** none. Do it.

---

## 2. Positive patient identification at collection

**Size: 4–6 weeks.** Cheap now that Code 128 rendering exists, and the highest
patient-safety value per unit of effort on this list.

Wrong-blood-in-tube is the error that kills people, and it happens at the
bedside, before anything this system controls today.

1. **Wristband format configuration.** Hospitals encode wristbands differently
   (raw MRN, prefixed, check-digited, sometimes a different identifier
   entirely). A parser configured per site, not a hard-coded assumption.
2. **Collection screen** for a tablet or handheld: scan wristband → resolve
   patient → show the outstanding collection → scan or print the tube label →
   confirm.
3. **Mismatch is a refusal, and is recorded.** A scan that does not match the
   order must stop the collection and raise an exception queue item. A silent
   mismatch is worse than no scanning.
4. **Offline capability.** Ward wifi is universally poor. The round is
   downloaded, collections are recorded locally, and sync happens on return —
   with conflict handling for an order cancelled meanwhile.
5. **Collector and time come from the scan**, not from a form filled in
   afterwards at the bench.
6. Audit the match event itself, so "was the wristband actually scanned" is
   answerable per specimen.
7. Report: collections by scanned-vs-manual, to show the practice is real.

**Decisions:** which device (hospital-issued handheld, personal phone, cart
tablet) and who owns it; whether manual override is permitted and who may use
it.

**Depends on:** nothing. Labels already exist.

---

## 3. Send-outs and reference laboratory management

**Size: 8–12 weeks.** High operational value, low regulatory risk, no
architectural change. The strongest candidate to do first among the substantial
items.

Every laboratory sends work out, and today Dx cannot represent it at all — so
send-outs are invisible in turnaround figures, which is exactly where they do
the most damage.

1. **`ReferenceLaboratory`**: name, accreditation number, contact, courier
   schedule, cut-off times.
2. **Send-out catalogue**: local test code ↔ reference lab code, their price,
   their stated turnaround, specimen requirements (volume, container,
   stability, temperature).
3. **Routing**: which tests go out, to which laboratory, conditionally (a test
   done in-house on weekdays and sent out at weekends is the normal case).
4. **Requirement enforcement**: refuse a send-out whose specimen cannot meet
   the reference lab's volume or stability requirement, at the point of
   decision rather than on rejection three days later.
5. **Manifest and despatch**: packing list, courier tracking reference,
   temperature category, despatch time.
6. **Outbound interface**: HL7 `ORM` to the reference laboratory, their API, or
   a portal export for those with neither.
7. **Inbound results**: their codes mapped back to yours; handling results that
   arrive only as PDF, which many do.
8. **The report must name the performing laboratory** (CLIA §493.1291(a)), with
   its accreditation number, for every sent-out analyte.
9. **Turnaround tracking for send-outs**, and chasing: anything past its
   expected return onto the exception queue.
10. **Cost per send-out**, feeding a bring-in-house business case.

**Decisions:** which reference laboratories, and whether their interfaces are
available (many are portal-only, which changes item 6 substantially).

---

## 4. High availability and disaster recovery

**Size: 4–8 weeks**, mostly infrastructure rather than application code.

The application is already stateless behind the database. What is missing is
everything around it.

1. **Agree RPO and RTO with the laboratory.** Not a technical decision. "How
   much work may we lose" and "how long may we be down" have different answers
   for a blood gas service and a histology department.
2. **PostgreSQL streaming replication**, with a documented failover procedure.
   Decide automatic promotion versus manual — automatic failover on a system
   with a hash-chained audit trail deserves thought, because a split brain
   produces two divergent chains.
3. **Multiple application instances.** Requires the shared cache already
   flagged by `dx.W001`; database-backed sessions already work.
4. **Verify the audit recorder under concurrency.** N instances means N
   recorder threads appending to one chain. The advisory lock should serialise
   them correctly — prove it with a load test rather than assuming.
5. **Point-in-time recovery**: WAL archiving, not only `pg_dump`. A nightly
   dump has a 24-hour RPO, which nobody actually accepts when asked directly.
6. **A tested restore.** On a schedule, to a scratch environment, including the
   audit trigger drop and reinstate and a full chain verification. An untested
   backup is a hypothesis.
7. **Disaster recovery site**, with a documented and annually exercised
   invocation.
8. **Load test at target volume** and publish the number. "How many results a
   day" is the second question in any procurement and there is currently no
   answer.
9. **Alerting** on replication lag and on the metrics now exposed at
   `/metrics` — particularly `dx_audit_recorder_running` and
   `dx_audit_queue_depth`.

**Decisions:** RPO/RTO; cloud or on-premises; whether the hospital's existing
database team owns Postgres.

---

# Substantial, self-contained

## 5. Advanced quality control

**Size: 8–12 weeks.** Westgard multirules are implemented; everything modern
around them is not.

1. **Peer group comparison.** Export to the laboratory's QC programme, import
   peer mean/SD/CV, report bias against peer. Catches the systematic shift that
   looks perfectly in-control against your own targets.
2. **Patient-based real-time QC (moving averages).** Rolling means of patient
   results with per-analyte truncation limits and alarm thresholds, plus a
   tuning tool that replays historic data to set them. Genuinely valuable and
   poorly implemented commercially — it detects drift between QC runs, which is
   where most of it happens.
3. **Six Sigma metrics** per analyte from total allowable error, bias and CV.
4. **Rule selection driven by sigma**, so a high-sigma method is not burdened
   with rules that only produce false rejections.
5. **QC scheduling and lockout by shift**, rather than the current 24-hour
   window.
6. **Lot-to-lot verification** workflow with acceptance criteria, currently a
   manual paper exercise everywhere.

**Decisions:** which QC programme; TEa source (CLIA, RCPA, biological
variation) — this is a laboratory decision with real consequences.

---

## 6. Accessibility to WCAG 2.1 AA

**Size: 4–8 weeks**, excluding item 1 which should be done immediately.

Currently unaudited, and almost certainly non-conformant: 36 `<label>` elements
and 6 `aria-*` attributes across the whole template set.

1. **Automated audit** (axe-core or pa11y) across every route, wired into CI.
   Catches perhaps a third of issues and stops regression.
2. **Manual keyboard traversal** of the clinical workflows — accessioning,
   result entry, verification. Result entry is keyboard-driven already, which
   helps.
3. **Screen reader pass** (NVDA or JAWS) on result entry and the exception
   queue.
4. **Form semantics**: every input labelled, error messages associated with
   their field, required fields marked programmatically.
5. **Landmarks, skip links, focus management** — particularly focus after a
   form error or a modal.
6. **Live regions** for the exception queue and messages.
7. **Print styles** verified for reports and the downtime pack.
8. **VPAT / accessibility conformance report** if procurement asks, which in
   public-sector procurement it will.

**Decisions:** target level (AA is standard; AAA is not realistic for a
data-dense clinical application).

---

## 7. Point-of-care testing

**Size: 6–10 weeks**, plus per-vendor interface work.

`POCT1A` exists as a protocol choice with nothing behind it.

1. **`PoctDevice`**: serial number, type, ward/location, assigned operators.
2. **POCT1-A interface**, or the vendor's middleware (Radiometer, Abbott,
   Roche, Siemens each have their own).
3. **Operator competency lockout.** The control that makes POCT defensible: a
   device refuses an operator without current competency. Requires pushing the
   competency list *to* the device, not just holding it here.
4. **Result capture** with device, operator and location, flagged as POCT on
   the report — a ward glucose and a laboratory glucose are not interchangeable
   and the report must say which it is.
5. **QC on the device**, with lockout on failure, surfaced in the same QC
   screens as the main laboratory.
6. **Lot and reagent tracking** per device, including expiry lockout.
7. **Correlation studies** against the central laboratory method (a CAP
   requirement), with a workflow rather than a spreadsheet.
8. **Connectivity monitoring.** A POCT device that stopped uploading a week ago
   is invisible today; this belongs on the exception queue.

**Decisions:** which devices, and whether the site already runs vendor
middleware — if it does, interface to that rather than to each device.

---

## 8. Business intelligence and de-identified extracts

**Size: 6–10 weeks.**

1. **Decide the model**: a read replica queried directly, or an ETL to a star
   schema. For a single laboratory, a replica plus views is usually enough and
   far less to maintain.
2. **De-identification**, which is the part with real value beyond reporting:
   HIPAA Safe Harbor removal of the eighteen identifiers, date shifting per
   patient, and a pseudonym that is stable within an extract and not reversible
   outside it. Reuses the tokenisation already in `apps/audit/redaction.py`.
3. **Dimensional model** if going that way: `fact_result`, `fact_order`,
   `dim_patient`, `dim_test`, `dim_time`, `dim_requester`.
4. **Scheduled extract** with watermarking and a recorded extract manifest.
5. **Connect the hospital's existing tool** — Power BI, Tableau, whatever is
   already licensed. Do not build a visualisation layer.
6. **A small set of canned reports**: volume, turnaround by discipline, repeat
   and rejection rates, QC performance, cost per test.
7. **Research extract workflow** with an IRB/ethics reference recorded against
   each extract, and the extract logged as a disclosure.

**Decisions:** which BI tool; whether research access is in scope, which brings
ethics approval workflow with it.

**Unblocks:** non-production environments with realistic, non-identifiable
data — currently impossible, and a prerequisite for item 17.

---

## 9. Electronic laboratory reporting to public health

**Size: 6–10 weeks of engineering, 3–6 months of calendar** — most of it
waiting on the health authority, not coding.

Notifiable conditions are *detected* today; nothing transmits them.

1. **Jurisdiction rules**: the reportable conditions list, timeframes and
   destination, which differ by country and often by region.
2. **Message profile**: HL7 v2.5.1 ELR against the relevant implementation
   guide, or FHIR where the jurisdiction has moved to it.
3. **Coded results.** ELR requires LOINC for the test and SNOMED CT for the
   organism or finding. This is the item that makes the terminology gap
   material rather than theoretical.
4. **Transport**: usually a national or state gateway with its own onboarding,
   credentials and test harness.
5. **Acknowledgement handling and resubmission**, onto the exception queue.
6. **Onboarding and validation** with the health department: parallel
   submission, message validation, sign-off.

**Decisions:** jurisdiction; whether SNOMED CT is licensed, which item 3
requires.

---

## 10. Internationalisation

**Size: 6–10 weeks for the framework**, plus per-language translation cost.

`USE_I18N` is on and nothing is translated.

1. **Wrap user-facing strings** in `gettext` — roughly three thousand across
   templates and Python.
2. **`LocaleMiddleware`**, a language selector, and a per-user preference.
3. **Extraction and compilation** wired into CI so an untranslated string is
   visible before release.
4. **Locale-aware dates, times and numbers** — a decimal comma is not cosmetic
   in a result value.
5. **Units.** Decide whether to convert (mg/dL ↔ mmol/L) or only to display
   what is stored. Converting is a clinical decision with a safety dimension
   and should not be a locale setting.
6. **The help library is the bulk of the cost** — 80 topics, around 45,000
   words. Decide explicitly whether it is translated, partially translated
   (the tutorials only), or stays English.
7. **The downtime pack and specimen labels** matter most clinically and should
   be translated first, not last.
8. **Right-to-left support** if Arabic or Hebrew is in scope — a layout
   exercise, not a string exercise.

**Decisions:** which languages; whether the help library is in scope; who
reviews clinical terminology, because a mistranslated interpretive comment is a
clinical risk and not a typo.

---

# Architectural

## 11. Multi-site and multi-tenancy

**Size: 8–12 weeks**, and the highest-risk item here because it touches every
table.

**Do not start this without deciding what Dx is.** A network of laboratories
running separate instances is a legitimate answer, and for a handful of sites
it is the better one.

1. **Decide the isolation model.** Shared schema with a facility column,
   schema-per-tenant, or database-per-tenant. Recommendation: shared schema
   with a `facility` foreign key — the audit chain is global and splitting it
   across schemas is genuinely unpleasant.
2. **`Facility`**: code, name, address, accreditation number, timezone, active.
3. **Decide what is per-site and what is shared.** LOINC and ICD-10 are
   network-wide. The test catalogue, reference intervals, QC targets and
   decision rules are arguably either, and the answer determines how much of
   the work is data modelling versus governance.
4. **Add the foreign key** to root entities and backfill a default facility.
5. **Scoped access**: `User.facilities`, a current facility on the session, a
   switcher, and a default manager that filters. Then audit every query that
   bypasses it — this is where tenancy bugs live.
6. **Accession numbering per facility**, including the advisory lock key, which
   currently serialises globally.
7. **Patient identity across sites.** The largest single decision: is an MRN
   facility-scoped or network-wide? Network-wide means an enterprise master
   patient index, with matching, merging and the unmerge nobody wants to think
   about.
8. **Cross-facility referral**: an order raised at one site, performed at
   another, reported by both.
9. **The audit trail stays one chain**, with facility on the event. The PHI
   barrier must also bar cross-facility access.
10. **Network-level reporting** alongside per-facility.
11. **Tests that a user of facility A cannot reach facility B's data** by URL,
    by API, by export, by search, or through the exception queue.

**Decisions:** isolation model; MRN scope; which master files are shared. All
three are irreversible in practice.

---

# Separate products in all but name

Each of these is a discipline with its own regulations, its own vocabulary and
its own expert. The recommendation for all four is the same: **integrate with a
dedicated system unless this discipline is the reason Dx exists.**

## 12. Anatomic pathology depth

**Size: 4–6 months**, plus 3–4 for digital pathology.

Blocks and slides are tracked. A hospital AP department needs considerably
more.

1. **Case above specimen**: parts (A, B, C), blocks, slides, stains.
2. **Grossing**: templates or dictation, cassette allocation, block key.
3. **Histology workflow**: processing, embedding, microtomy, H&E, specials,
   immunohistochemistry, with section QC.
4. **Slide tracking** by barcode through trays and racks.
5. **Synoptic reporting.** The big one: CAP electronic Cancer Checklists,
   parsed from the published protocols, rendered as structured forms with
   required-element validation, emitted as structured data rather than prose.
   The content is licensed.
6. **Sign-out states**: draft, preliminary, final — with addendum distinct from
   amendment, because they mean different things to a clinician.
7. **Intradepartmental consultation** and second opinion with concurrence
   recorded.
8. **Frozen section**: intraoperative turnaround clock, deferred diagnosis, and
   the frozen-to-final discrepancy log a quality programme depends on.
9. **Prior case retrieval.** A pathologist always asks whether this patient has
   been seen before; today the answer requires a search.
10. **Cytology screening limits** — CLIA §493.1274 caps a screener at 100
    slides per 24 hours, with a 10% rescreen and a discrepancy workflow. This
    is enforced counting, not reporting.
11. **Digital pathology**: whole-slide image ingestion, a viewer, slide-to-case
    linkage, and storage planning — a single slide is 1–4 GB, which changes the
    infrastructure conversation entirely.

**Decisions:** whether CAP eCC is licensed; whether digital pathology is in
scope, which roughly doubles the item.

---

## 13. Blood bank and transfusion medicine

**Size: 6–9 months.** The strongest "do not build this" on the list.

21 CFR 606/610/640 and AABB standards, with a failure mode that kills people
within minutes. It needs a transfusion scientist as owner throughout and
almost certainly formal computer system validation.

1. **Scope the regulatory position**: hospital transfusion service or
   FDA-registered establishment. Different rules entirely.
2. **Unit inventory**: ISBT 128 unit number, component type, ABO/Rh, collection
   and expiry, quarantine states.
3. **ISBT 128 labelling** — a different barcode discipline from specimen
   labels, with its own data identifiers and check characters.
4. **Patient testing**: ABO/Rh with the second-determination rule, antibody
   screen, identification panel, direct antiglobulin test.
5. **Historical record check.** The single most important control in the
   module: a patient's historical ABO and antibody history must be checked
   before any issue, and a discrepancy must stop everything.
6. **Crossmatch**, serological and electronic — electronic crossmatch has
   strict eligibility rules (no current or historical antibodies, two
   concordant ABO determinations) that must be enforced, not advisory.
7. **Special requirements**: irradiated, CMV-negative, phenotype-matched,
   washed. These attach to the *patient*, persist for life, and must be
   enforced at issue.
8. **Allocation, issue and return**, with the 30-minute time-out-of-fridge
   rule.
9. **Emergency uncrossmatched issue**, with documented authorisation — the path
   that must be fast and must still be recorded.
10. **Administration record** with vital signs.
11. **Transfusion reaction** workflow, investigation, and haemovigilance
    reporting.
12. **Look-back and recall.**
13. **MSBOS and crossmatch-to-transfusion ratio** reporting.
14. **Fridge and temperature monitoring** interface.

**Decisions:** build or integrate. The honest recommendation is integrate.

---

## 14. Molecular and next-generation sequencing

**Size: 6–9 months.** Needs a clinical genomic scientist throughout.

1. **Assay definitions**: panel and gene lists, reference genome build,
   coverage thresholds.
2. **Wet-lab tracking**: extraction, library preparation, indexing, pooling,
   run — with reagent lot at every step.
3. **Sequencer interface**: run metadata and QC metrics (Q30, cluster density,
   on-target rate, coverage uniformity).
4. **Pipeline hand-off.** Secondary analysis belongs in a bioinformatics
   pipeline, not here; Dx ingests the VCF and holds pointers to BAM and FASTQ.
5. **Variant model**: HGVS nomenclature, transcript, zygosity, allele fraction,
   coverage at position.
6. **Versioned annotation ingestion** (ClinVar, gnomAD, OMIM). Versions matter:
   reinterpretation depends on knowing what was known when.
7. **Classification workflow**: ACMG/AMP criteria with evidence codes, tier
   assignment, two-person review.
8. **Variant knowledge base** with reinterpretation triggers when evidence
   changes.
9. **Reporting**: primary findings, secondary findings against the ACMG list,
   variants of uncertain significance, and an explicit limitations statement.
10. **Reanalysis**: the workflow that asks whether an old negative should be
    re-examined against current knowledge. Clinically important, almost never
    implemented.
11. **Confirmation** (Sanger) tracking.
12. **Consent linkage** — secondary findings require specific consent, and
    reporting one without it is a serious matter.

**Decisions:** which assays; whether bioinformatics is in-house; consent model.

---

## 15. Revenue cycle

**Size: 4–6 months**, and **almost entirely jurisdiction-specific**.

A US deployment needs all of this. A UK or Sri Lankan one needs almost none.
**Decide the target market before writing any of it** — this is the item most
likely to be built and then discarded.

1. **Payer and plan model**, fee schedules, contract rates.
2. **Eligibility check** (X12 270/271), real time, at accessioning.
3. **Medical necessity**: LCD/NCD rules mapping CPT to ICD-10, with advance
   beneficiary notice generation when a test fails them. The ICD-10 work
   already done is the foundation.
4. **Charge capture**: CPT/HCPCS per test, modifiers, panel unbundling rules.
5. **Claim generation** (X12 837P) and clearinghouse submission.
6. **Remittance posting** (X12 835), denial codes, and a denial worklist.
7. **Patient statements, client billing, split billing.**
8. **Prior authorisation** tracking.
9. **Compliance**: no charge for a test not performed. The link between charge
   and result status must be enforced, not assumed.
10. **Accounts receivable ageing** and revenue reporting.

**Decisions:** target jurisdiction, before anything else.

---

## 16. Patient portal

**Size: 3–5 months**, and the **highest security risk on this list** — it is
the first internet-facing component holding patient data.

1. **Patient identity and enrolment**: invitation, identity proofing, and a
   credential store **separate from the staff realm**. Sharing an auth realm
   between staff and patients is the mistake to avoid at the outset.
2. **Proxy access**: parent, guardian, carer — with age-based transitions,
   because a thirteen-year-old's access rules change and the system has to
   handle that date arriving.
3. **Release rules.** Immediate release is the Cures Act default; the
   exceptions are narrow and must be documented per decision, not applied as a
   blanket delay.
4. **Sensitive results**: HIV, genetics, oncology, safeguarding concerns —
   jurisdiction-specific and requiring clinical input.
5. **Lay presentation**: reference ranges a patient can read, plain-language
   context, and explicit "discuss this with your doctor" framing for anything
   abnormal.
6. **Information blocking compliance**: the eight exceptions, with a recorded
   basis whenever one is relied on.
7. **Patient access audited distinctly** from staff access.
8. **Enumeration and abuse protection**: rate limiting, account lockout that
   cannot be used to deny a patient access, and a security review before it is
   exposed.

**Decisions:** jurisdiction; sensitive-result policy, which is a clinical
governance decision and not a configuration value.

---

# Ongoing

## 17. Validation and product maturity

**Size: 3–6 months to establish, then continuous.**

Required to deploy in a regulated laboratory regardless of features.

1. **Requirements traceability matrix**: requirement → design → test. The 604
   tests are the raw material; what is missing is the mapping.
2. **IQ/OQ/PQ protocol templates** the laboratory executes at installation.
3. **GAMP 5 category assessment** and a validation plan.
4. **Release process**: versioning, release notes, a regression gate, and a
   rehearsed upgrade including migrations.
5. **Non-production environments with de-identified data** — depends on item 8.
6. **Penetration test** and remediation, before any internet-facing component.
7. **SOC 2 Type II or ISO 27001** if Dx is sold rather than deployed in-house.
8. **Support model**: SLA, escalation path, on-call, and a defined patch
   cadence for security fixes.

**Decisions:** in-house deployment or commercial product. Almost everything
here follows from that one answer.

---

## A suggested order

Ignoring the separate-product items, which need their own decision:

| | Item | Size | Why here |
| --- | --- | --- | --- |
| 1 | Colour-independent flags | days | Patient-safety defect, trivially fixed |
| 2 | Positive patient ID | 4–6 wk | Highest safety value per unit of effort; unblocked by labels |
| 3 | Send-outs | 8–12 wk | High operational value, low risk, no architecture change |
| 4 | HA/DR | 4–8 wk | Deployment-blocking; mostly infrastructure |
| 5 | Advanced QC | 8–12 wk | Differentiating; PBRTQC is poorly served commercially |
| 6 | Accessibility | 4–8 wk | Procurement-blocking in the public sector |
| 7 | BI and de-identification | 6–10 wk | Unblocks non-production environments for item 17 |

Then the architectural decision: **multi-site, or depth in one discipline?**
They compete for the same time and the answer determines what Dx is for.
