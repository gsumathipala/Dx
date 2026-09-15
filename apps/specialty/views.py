"""Histopathology and microbiology workbenches.

The bench screens are written out below; the supporting registries are declared
as ``CrudResource`` objects in ``urls.py``.
"""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES
from apps.specialty.models import (
    Antibiotic, HistoBlock, HistoSlide, MicroCulture, SusceptibilityResult,
)

LAB_STAFF = tuple(LAB_STAFF_ROLES)
MANAGERS = tuple(MANAGEMENT_ROLES)


class HistoBlockForm(forms.ModelForm):
    class Meta:
        model = HistoBlock
        fields = ["specimen", "block_id", "tissue_type", "status", "grossed_by", "archive_location"]


class HistoSlideForm(forms.ModelForm):
    class Meta:
        model = HistoSlide
        fields = ["block", "slide_id", "stain", "status", "stained_by"]


class MicroCultureForm(forms.ModelForm):
    class Meta:
        model = MicroCulture
        fields = ["order", "specimen", "test", "status", "incubator_location",
                  "setup_time", "preliminary_result", "final_result"]
        widgets = {"setup_time": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class SusceptibilityForm(forms.ModelForm):
    class Meta:
        model = SusceptibilityResult
        fields = ["culture", "organism", "antibiotic", "mic", "zone_diameter",
                  "interpretation", "reported", "standard"]


class AntibioticForm(forms.ModelForm):
    class Meta:
        model = Antibiotic
        fields = ["name", "code", "drug_class", "tier", "active"]


@login_required
def histology(request):
    """Block and slide tracking through the histopathology workflow."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit access to histopathology.")
        return redirect("operations:dashboard")

    return render(request, "specialty/histology.html", {
        "blocks": HistoBlock.objects.select_related("specimen", "specimen__order")
                  .order_by("-timestamp")[:60],
        "slides": HistoSlide.objects.select_related("block").order_by("-timestamp")[:60],
        "by_status": {
            status.label: HistoBlock.objects.filter(status=status.value).count()
            for status in HistoBlock.Status
        },
    })


@login_required
def microbiology(request):
    """Culture workbench and antibiogram."""
    if request.user.role not in LAB_STAFF:
        messages.error(request, "Your role does not permit access to microbiology.")
        return redirect("operations:dashboard")

    cultures = (
        MicroCulture.objects.select_related("order", "specimen", "test")
        .prefetch_related("susceptibilities__antibiotic")
        .order_by("-setup_time")[:60]
    )
    return render(request, "specialty/microbiology.html", {
        "cultures": cultures,
        "by_status": {
            status.label: MicroCulture.objects.filter(status=status.value).count()
            for status in MicroCulture.Status
        },
        "resistant": SusceptibilityResult.objects.filter(
            interpretation=SusceptibilityResult.Interpretation.RESISTANT
        ).select_related("antibiotic")[:25],
    })
