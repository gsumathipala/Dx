"""The in-application help library."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from apps.help import library


def _common(request):
    return {
        "sections": library.load(),
        "help_query": request.GET.get("q", ""),
    }


@login_required
def index(request):
    """The library's front page: sections, and where to start."""
    sections = library.load()
    return render(request, "help/index.html", {
        **_common(request),
        "topic_count": sum(len(section.topics) for section in sections),
        "tutorials": [
            topic for topic in library.all_topics()
            if "tutorial" in topic.keywords
        ],
    })


@login_required
def section(request, section_slug: str):
    found = library.get_section(section_slug)
    if found is None:
        raise Http404("No such help section.")
    return render(request, "help/section.html", {**_common(request), "section": found})


@login_required
def topic(request, section_slug: str, topic_slug: str):
    found = library.get_topic(section_slug, topic_slug)
    if found is None:
        raise Http404("No such help topic.")

    html, toc = found.render()
    previous_topic, next_topic = library.neighbours(found)

    return render(request, "help/topic.html", {
        **_common(request),
        "section": library.get_section(section_slug),
        "topic": found,
        "content": html,
        "toc": toc,
        "previous_topic": previous_topic,
        "next_topic": next_topic,
    })


@login_required
def search(request):
    query = (request.GET.get("q") or "").strip()
    return render(request, "help/search.html", {
        **_common(request),
        "query": query,
        "hits": library.search(query) if query else [],
    })


@login_required
def contextual(request):
    """Jump from a screen to the topic that explains it.

    The sidebar's help link passes the current view name, so "Help" from the
    quality control screen lands on quality control rather than the front page.
    """
    view_name = request.GET.get("for", "")
    destination = CONTEXT_MAP.get(view_name)
    if destination:
        return redirect("help:topic", *destination.split("/"))
    return redirect("help:index")


#: Screen → help topic. Anything unmapped falls back to the library index.
CONTEXT_MAP = {
    "operations:dashboard": "getting-started/the-interface",
    "operations:search": "getting-started/the-interface",
    "laboratory:accessioning": "laboratory-workflow/accessioning",
    "laboratory:receiving": "laboratory-workflow/specimen-reception",
    "laboratory:results": "laboratory-workflow/entering-results",
    "laboratory:result_entry": "laboratory-workflow/entering-results",
    "laboratory:phlebotomy_list": "laboratory-workflow/phlebotomy",
    "quality:qc": "quality/running-quality-control",
    "quality:equipment_list": "quality/equipment-and-calibration",
    "clinical:critical_values": "clinical-decision-support/critical-values",
    "clinical:delta_rule_list": "clinical-decision-support/delta-checks",
    "clinical:reflex_rule_list": "clinical-decision-support/reflex-testing",
    "clinical:range_list": "clinical-decision-support/reference-intervals",
    "clinical:calculated_list": "clinical-decision-support/calculated-tests",
    "clinical:epidemiology": "clinical-decision-support/notifiable-conditions",
    "reporting:reports": "reporting/patient-reports",
    "reporting:amend": "reporting/amended-reports",
    "reporting:document_list": "reporting/controlled-documents",
    "audit:trail": "security-and-audit/the-audit-trail",
    "audit:integrity": "security-and-audit/chain-integrity",
    "accounts:user_list": "security-and-audit/managing-users",
    "compliance:dashboard": "quality/quality-management",
    "compliance:capa_list": "quality/corrective-actions",
    "compliance:pt_list": "quality/proficiency-testing",
    "compliance:validation_list": "quality/method-validation",
    "operations:backup": "administration/backup-and-restore",
    "operations:settings_index": "administration/configuration",
    "inventory:item_list": "inventory-and-operations/inventory",
    "interop:interface_list": "interoperability/instrument-interfaces",
    "billing:invoice_list": "inventory-and-operations/billing",
    "specialty:histology": "inventory-and-operations/histopathology",
    "specialty:microbiology": "inventory-and-operations/microbiology",
}
