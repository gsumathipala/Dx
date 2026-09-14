"""Histopathology and microbiology workbenches."""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from apps.common.constants import LAB_STAFF_ROLES, MANAGEMENT_ROLES
from apps.common.views import DxCreateView, DxListView, DxUpdateView
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


class HistoBlockListView(DxListView):
    model = HistoBlock
    required_roles = LAB_STAFF
    page_title = "Histology blocks"
    search_fields = ["block_id", "tissue_type"]
    columns = [("Block", "block_id", "mono"), ("Tissue", "tissue_type", ""),
               ("Status", "status", ""), ("Grossed by", "grossed_by", ""),
               ("Archive", "archive_location", "")]
    create_url_name = "specialty:block_create"
    update_url_name = "specialty:block_update"


class HistoBlockCreateView(DxCreateView):
    model = HistoBlock
    form_class = HistoBlockForm
    required_roles = LAB_STAFF
    page_title = "block"
    success_url = reverse_lazy("specialty:blocks")


class HistoBlockUpdateView(DxUpdateView):
    model = HistoBlock
    form_class = HistoBlockForm
    required_roles = LAB_STAFF
    page_title = "block"
    success_url = reverse_lazy("specialty:blocks")


class HistoSlideListView(DxListView):
    model = HistoSlide
    required_roles = LAB_STAFF
    page_title = "Histology slides"
    search_fields = ["slide_id", "stain"]
    columns = [("Slide", "slide_id", "mono"), ("Block", "block.block_id", "mono"),
               ("Stain", "stain", ""), ("Status", "status", ""), ("By", "stained_by", "")]
    create_url_name = "specialty:slide_create"
    update_url_name = "specialty:slide_update"


class HistoSlideCreateView(DxCreateView):
    model = HistoSlide
    form_class = HistoSlideForm
    required_roles = LAB_STAFF
    page_title = "slide"
    success_url = reverse_lazy("specialty:slides")


class HistoSlideUpdateView(DxUpdateView):
    model = HistoSlide
    form_class = HistoSlideForm
    required_roles = LAB_STAFF
    page_title = "slide"
    success_url = reverse_lazy("specialty:slides")


class CultureListView(DxListView):
    model = MicroCulture
    required_roles = LAB_STAFF
    page_title = "Cultures"
    columns = [("Order", "order.accession_number", "mono"), ("Status", "status", ""),
               ("Incubator", "incubator_location", ""), ("Set up", "setup_time", "nowrap"),
               ("Hours", "incubation_hours", "")]
    create_url_name = "specialty:culture_create"
    update_url_name = "specialty:culture_update"

    def get_queryset(self):
        return super().get_queryset().select_related("order")


class CultureCreateView(DxCreateView):
    model = MicroCulture
    form_class = MicroCultureForm
    required_roles = LAB_STAFF
    page_title = "culture"
    success_url = reverse_lazy("specialty:cultures")


class CultureUpdateView(DxUpdateView):
    model = MicroCulture
    form_class = MicroCultureForm
    required_roles = LAB_STAFF
    page_title = "culture"
    success_url = reverse_lazy("specialty:cultures")


class SusceptibilityListView(DxListView):
    model = SusceptibilityResult
    required_roles = LAB_STAFF
    page_title = "Susceptibility results"
    search_fields = ["organism"]
    columns = [("Organism", "organism", ""), ("Antibiotic", "antibiotic.name", ""),
               ("MIC", "mic", ""), ("Zone", "zone_diameter", ""),
               ("Interpretation", "interpretation", ""), ("Reported", "reported", ""),
               ("Standard", "standard", "")]
    create_url_name = "specialty:susceptibility_create"

    def get_queryset(self):
        return super().get_queryset().select_related("antibiotic", "culture")


class SusceptibilityCreateView(DxCreateView):
    model = SusceptibilityResult
    form_class = SusceptibilityForm
    required_roles = LAB_STAFF
    page_title = "susceptibility result"
    success_url = reverse_lazy("specialty:susceptibilities")


class AntibioticListView(DxListView):
    model = Antibiotic
    required_roles = MANAGERS
    page_title = "Antibiotics"
    search_fields = ["name", "code"]
    columns = [("Name", "name", ""), ("Code", "code", "mono"),
               ("Class", "drug_class", ""), ("Tier", "tier", ""), ("Active", "active", "")]
    create_url_name = "specialty:antibiotic_create"
    update_url_name = "specialty:antibiotic_update"


class AntibioticCreateView(DxCreateView):
    model = Antibiotic
    form_class = AntibioticForm
    required_roles = MANAGERS
    page_title = "antibiotic"
    success_url = reverse_lazy("specialty:antibiotics")


class AntibioticUpdateView(DxUpdateView):
    model = Antibiotic
    form_class = AntibioticForm
    required_roles = MANAGERS
    page_title = "antibiotic"
    success_url = reverse_lazy("specialty:antibiotics")
