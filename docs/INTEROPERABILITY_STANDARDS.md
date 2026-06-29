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
    *   `ORM^O01`: Order Entry (EHR -> LIS).
    *   `ORU^R01`: Unsolicited Observation Result (LIS -> EHR).

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

### UCUM (Unified Code for Units of Measure)
*   **Purpose:** Unambiguous representation of units.
*   **Application:** Converting `mg/dL` vs `mmol/L` safely.
    *   *Example:* `mg/dL`, `g/L`.

## 3. Security & Privacy Standards

### SMART on FHIR / OAuth 2.0
*   **Purpose:** Secure authorization for API access.
*   **Requirement:** Ensure external EHRs authenticate via OAuth2 scopes (e.g., `patient/*.read`) rather than static API keys.

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

- [ ] **Map Local Codes:** Ensure all TESTS in `db.json` have a valid `loincCode`.
- [ ] **Build FHIR Facade:** Create `GET /api/fhir/DiagnosticReport` endpoint.
- [ ] **Implement mTLS:** Secure the API Gateway with certificate-based auth.
- [ ] **Validate Units:** Enforce UCUM standard units in the Result Entry forms.
