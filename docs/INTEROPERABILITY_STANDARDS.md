# Dx LIS - Interoperability & Standards Guide

## Overview
This document outlines the international standards required to connect Dx LIS with Electronic Patient Records (EPR/EHR) and Hospital Information Systems (HIS). Compliance with these standards ensures seamless data exchange, patient safety, and regulatory adherence.

## 1. Transport & Messaging Standards

### HL7 FHIR R4 (Fast Healthcare Interoperability Resources)
*   **Purpose:** Modern, web-based API standard for exchanging healthcare data.
*   **Usage:** best for connecting to modern EHRs (Epic, Cerner, Apple Health) and mobile apps.
*   **Key Resources for LIS:**
    *   `ServiceRequest`: Represents the Lab Order (Test Request).
    *   `Specimen`: Details about the sample (swab, blood) and collection.
    *   `Observation`: The individual test result (e.g., Glucose level).
    *   `DiagnosticReport`: The compiled clinical report grouping observations.
*   **Implementation Strategy:** Expose a RESTful API returning JSON resources conforming to US Core or regional profiles.

### HL7 v2.5.1 / v2.9
*   **Purpose:** The traditional, pipe-delimited messaging standard used by 95% of hospitals for internal interfaces.
*   **Usage:** Socket-based (MLLP) communication for high-volume, real-time data.
*   **Key Messages:**
    *   `ORM^O01` / `OML^O21`: Order Entry (EHR → LIS) — **implemented**, at
        `POST /api/middleware/hl7/`. New orders (`ORC-1 = NW`) and
        cancellations (`CA`) are both handled, keyed on the placer order
        number so a retransmission does not accession a second specimen.
    *   `ADT^A01/A04/A08/A28/A31`: Patient registration and update
        (HIS → LIS) — **implemented**, same endpoint.
    *   `ADT^A40`: Patient merge — **implemented**. Orders are repointed onto
        the surviving MRN and the retired record is kept, flagged as merged,
        because the audit trail refers to it.
    *   `ORU^R01`: Unsolicited Observation Result (LIS → EHR) —
        **implemented**, at `GET /interop/hl7/oru/<order>/`.
    *   `QBP^Q11` / `RSP^K11`: Specimen work-list query (analyser → LIS) —
        **implemented**. See host query below.
    *   `ACK`: Every inbound message is acknowledged with `AA`, `AE` or `AR`.
        `AE` and `AR` are kept distinct: a sender that gets `AE` knows its
        message is wrong, one that gets `AR` knows it is malformed.

### Bidirectional instrument interfacing (host query)

*   **Purpose:** An analyser reads a specimen barcode and asks the LIS what to
    run on it, instead of running a fixed panel or being keyed by hand.
*   **Usage:** ASTM E1394 `Q` records, or HL7 `QBP^Q11`, answered by the
    instrument server; the LIS answers over
    `POST /api/middleware/query/`.
*   **Why it matters:** without it, either every specimen is run for every
    test the analyser offers — consuming reagent that then cannot be used on a
    request that needed it — or somebody keys the request into the analyser,
    which is the transcription error the interface existed to remove.
*   **Safety:** the LIS returns only tests that have no result yet, and only
    for an order that is still open. An analyser re-running a verified result
    would silently overwrite a report somebody has already acted on. An
    interface configured unidirectional is refused outright.

### RESTful JSON API

*   **Purpose:** What a hospital's own developers want — the ward dashboard,
    the audit extract, the research pull — as opposed to what its integration
    engine wants.
*   **Base:** `/api/v1/`. Client credentials, per-resource scopes, pagination,
    rate limiting. See [API.md](API.md).
*   **Events:** signed webhooks for `order.created`, `result.verified`,
    `report.released`, `critical_value.raised` and others, so a subscriber is
    told rather than polling.

## 2. Semantic & Coding Standards

### LOINC (Logical Observation Identifiers Names and Codes)
*   **Purpose:** Universal standard for identifying laboratory observations.
*   **Application:** Every "Test Definition" in Dx must map to a specific LOINC code.
    *   *Example:* `2345-7` = Glucose [Mass/volume] in Serum or Plasma.
*   **Status:** Dx has a `loincCode` field in the database `tests` schema.

### SNOMED CT (Systematized Nomenclature of Medicine)
*   **Purpose:** Comprehensive clinical terminology for qualitative results and findings.
*   **Application:** Coding "Organism" names in Microbiology or "Morphology" in Histology.
    *   *Example:* `115329001` = MRSA (finding).
*   **Status:** not implemented. SNOMED CT requires a licence in most
    jurisdictions and a terminology server to be useful; a partial local copy
    would be worse than none.

### ICD-10 (International Classification of Diseases)
*   **Purpose:** Coding the clinical indication a test was requested for.
*   **Application:** Three separate uses, which pull in different directions —
    clinical context for the decision rules (a sodium of 128 means something
    different on a patient already coded E87.1), medical necessity for a claim,
    and coded indications for audit and epidemiology.
*   **Status:** **implemented**. `Icd10Code` is a lookup table maintained by
    the laboratory; diagnoses attach to an order as `OrderDiagnosis`, ranked,
    with the code and description denormalised so a 2026 record still reads
    correctly in 2031 after the catalogue row has been revised. Codes arrive
    from `DG1` segments on inbound orders, or through the API.

### UCUM (Unified Code for Units of Measure)
*   **Purpose:** Unambiguous representation of units.
*   **Application:** Converting `mg/dL` vs `mmol/L` safely.
    *   *Example:* `mg/dL`, `g/L`.

## 3. Security & Privacy Standards

### SMART on FHIR / OAuth 2.0
*   **Purpose:** Secure authorization for API access.
*   **Requirement:** Ensure external EHRs authenticate via OAuth2 scopes (e.g., `patient/*.read`) rather than static API keys.
*   **Status:** not implemented. Dx uses scoped client credentials
    (`<key id>.<secret>`, hashed at rest, per-client scopes, rate limit,
    optional IP allow-list and expiry). This is honest about what it is: a
    *system* identity, not a delegated user authority. SMART's value is
    launching in a clinician's EHR session with their permissions, which is a
    different problem from a server-to-server integration and should not be
    approximated with a static secret dressed up as OAuth.

### ATNA (Audit Trail and Node Authentication)
*   **Profile:** IHE ATNA.
*   **Requirement:** Mutual TLS (mTLS) for all connections and centralized syslog auditing of every data access (already partially supported by Dx's internal audit trail).

## 4. Quality & Process Standards

### ISO 15189:2012 / 2022
*   **Scope:** "Medical laboratories — Requirements for quality and competence".
*   **Relevance:** Requires full traceability of:
    *   **User Identity:** Who released the result (handled by Dx Auth).
    *   **Equipment/Reagents:** Which lot # was used (handled by Inventory module).
    *   **Timestamps:** Exact time of collection, receipt, and verification.

### CLIA '88 (USA) / EU IVDR
*   **Requirement:** Two-tier verification (Technical vs Clinical) is a direct response to these regulatory requirements ensuring result accuracy before release.

## Developer Implementation Checklist

- [ ] **Map Local Codes:** Ensure every test definition carries a valid LOINC
      code. The catalogue screen accepts them; nothing enforces it, because a
      laboratory mid-migration would be blocked from entering results.
- [x] **FHIR facade:** `GET /interop/fhir/DiagnosticReport/<order>/` returns a
      DiagnosticReport, or a full Bundle with `?bundle=1`. Also available as
      `GET /api/v1/orders/<id>/report/?format=fhir`.
- [x] **HL7 v2 outbound:** `ORU^R01` at `GET /interop/hl7/oru/<order>/`.
- [x] **HL7 v2 inbound:** `ORM^O01`, `OML^O21` and `ADT` at
      `POST /api/middleware/hl7/`, acknowledged with `AA`/`AE`/`AR`.
- [x] **Bidirectional instruments:** host query over
      `POST /api/middleware/query/`; run the instrument server with
      `--host-query` and set the interface to bidirectional.
- [x] **RESTful API:** `/api/v1/` with scoped client credentials.
- [x] **Webhooks:** HMAC-SHA256 signed, replay-resistant, retried with backoff.
- [x] **ICD-10:** diagnosis codes on orders, from `DG1` segments or the API.
- [ ] **Implement mTLS:** Secure the API gateway with certificate-based auth.
      This is a deployment concern — terminate at the reverse proxy.
- [ ] **Validate Units:** Enforce UCUM units in the result entry forms.
- [ ] **SNOMED CT:** requires a licence and a terminology server.
