"""Blocks roles that must never see patient information.

The installer role exists so that whoever commissions and maintains the system
does not thereby acquire access to patient records. That separation is only
worth anything if it is enforced where the data is served, rather than by
leaving the links out of the menu — someone who can type a URL would otherwise
walk straight past it.

The barrier is a deny-list of URL namespaces and paths, applied to every
request. It is deliberately expressed as "which namespaces carry clinical
content" rather than "which namespaces may this role reach", so a newly added
clinical screen is blocked by default rather than exposed by omission.
"""
from __future__ import annotations

import re

from django.core.exceptions import PermissionDenied

#: URL namespaces whose screens can expose patient information.
CLINICAL_NAMESPACES = frozenset({
    "patients",     # demographics and the consolidated record
    "laboratory",   # orders, specimens, results, accessioning
    "clinical",     # critical values, delta flags, epidemiology
    "reporting",    # reports, cumulative reports, delivery
    "specialty",    # histopathology and microbiology
    "billing",      # invoices name the patient and the order
    "rules",        # rule executions record the patient facts a rule saw
    "api",          # the public API serves patient records
})

#: Namespaces an administrative role legitimately needs, whose screens carry no
#: patient content. Anything not listed here and not clinical is allowed.
SYSTEM_NAMESPACES = frozenset({
    "accounts", "operations", "audit", "compliance", "interop", "inventory",
    "quality", "admin", "help",
})

#: Individual views inside otherwise-permitted namespaces that do expose
#: patient content, named explicitly.
BARRED_VIEW_NAMES = frozenset({
    "compliance:phi_access_list",     # lists MRNs
    "compliance:disclosure_list",     # lists patients and recipients
    "operations:search",              # resolves patients and orders
    "operations:tracking",            # specimen custody, linked to orders
    "operations:storage",             # specimen placement
    "interop:fhir_report",            # a patient's report as FHIR
    "interop:hl7_oru",                # a patient's report as HL7
    "interop:host_query_list",        # specimen identifiers and ordered tests
    "operations:exception_list",      # accession numbers and clinical detail
    "operations:exception_detail",
    "compliance:subject_request_list",   # names a patient in every row
    "compliance:subject_request_detail",
})

#: Paths reachable without passing a namespace check.
BARRED_PATH_PATTERNS = (
    re.compile(r"^/patients/"),
    re.compile(r"^/results/"),
    re.compile(r"^/reports/"),
)

MESSAGE = (
    "The installer role has no access to patient or clinical data. This is a "
    "deliberate separation of duties: whoever maintains the system does not "
    "thereby gain access to patient records. Ask a clinical user for anything "
    "you need from this screen."
)


def is_barred(user, resolver_match, path: str) -> bool:
    """Whether this user must be refused this view."""
    if user is None or not user.is_authenticated:
        return False
    if user.may_see_patient_data:
        return False

    if any(pattern.match(path) for pattern in BARRED_PATH_PATTERNS):
        return True

    if resolver_match is None:
        # Unresolvable path: let Django return its own 404 rather than
        # implying something exists here.
        return False

    if resolver_match.view_name in BARRED_VIEW_NAMES:
        return True

    namespace = resolver_match.namespace or ""
    return namespace in CLINICAL_NAMESPACES


class PHIBarrierMiddleware:
    """Refuse patient-facing screens to roles barred from them.

    Runs after authentication and after the audit context is bound, so the
    refusal is attributable if it ever needs investigating.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # process_view runs once the URL has resolved, so the namespace and
        # view name are known without re-resolving the path.
        user = getattr(request, "user", None)
        if is_barred(user, request.resolver_match, request.path):
            raise PermissionDenied(MESSAGE)
        return None
