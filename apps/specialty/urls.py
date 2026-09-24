"""URL routes for the histopathology and microbiology screens.

Ordering matters here. ``CrudResource.urls()`` ends each resource with a
``<str:pk>/`` pattern, which matches **any** single path segment — so a
resource mounted at a prefix that is a parent of another's will swallow it.
Anything more specific must be listed first, and several entries below are
placed deliberately rather than alphabetically.
"""
from django.urls import path

from apps.common.views import CrudResource
from apps.specialty import views
from apps.specialty.models import (
    Antibiotic, HistoBlock, HistoSlide, MicroCulture, SusceptibilityResult,
)

app_name = "specialty"

blocks = CrudResource(
    "block", HistoBlock, views.HistoBlockForm,
    roles=views.LAB_STAFF, title="Histology blocks", singular="block",
    columns=[("Block", "block_id", "mono"), ("Tissue", "tissue_type", ""),
             ("Status", "status", ""), ("Grossed by", "grossed_by", ""),
             ("Archive", "archive_location", "")],
    search_fields=["block_id", "tissue_type"],
)

slides = CrudResource(
    "slide", HistoSlide, views.HistoSlideForm,
    roles=views.LAB_STAFF, title="Histology slides", singular="slide",
    columns=[("Slide", "slide_id", "mono"), ("Block", "block.block_id", "mono"),
             ("Stain", "stain", ""), ("Status", "status", ""), ("By", "stained_by", "")],
    search_fields=["slide_id", "stain"],
)

cultures = CrudResource(
    "culture", MicroCulture, views.MicroCultureForm,
    roles=views.LAB_STAFF, title="Cultures", singular="culture",
    columns=[("Order", "order.accession_number", "mono"), ("Status", "status", ""),
             ("Incubator", "incubator_location", ""), ("Set up", "setup_time", "nowrap"),
             ("Hours", "incubation_hours", "")],
)

susceptibilities = CrudResource(
    "susceptibility", SusceptibilityResult, views.SusceptibilityForm,
    roles=views.LAB_STAFF, title="Susceptibility results", singular="susceptibility result",
    columns=[("Organism", "organism", ""), ("Antibiotic", "antibiotic.name", ""),
             ("MIC", "mic", ""), ("Zone", "zone_diameter", ""),
             ("Interpretation", "interpretation", ""), ("Reported", "reported", ""),
             ("Standard", "standard", "")],
    search_fields=["organism"],
)

antibiotics = CrudResource(
    "antibiotic", Antibiotic, views.AntibioticForm,
    roles=views.MANAGERS, title="Antibiotics", singular="antibiotic",
    columns=[("Name", "name", ""), ("Code", "code", "mono"),
             ("Class", "drug_class", ""), ("Tier", "tier", ""), ("Active", "active", "")],
    search_fields=["name", "code"],
)

urlpatterns = [
    path("histology/", views.histology, name="histology"),
    path("microbiology/", views.microbiology, name="microbiology"),

    *blocks.urls("histology/blocks/"),
    *slides.urls("histology/slides/"),
    *cultures.urls("microbiology/cultures/"),
    *susceptibilities.urls("microbiology/susceptibilities/"),
    *antibiotics.urls("microbiology/antibiotics/"),
]
