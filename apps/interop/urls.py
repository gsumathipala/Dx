from django.urls import path

from apps.common.views import CrudResource
from apps.interop import views
from apps.interop.models import (
    Icd10Code, InstrumentInterface, InstrumentMessage, LoincCode,
)

app_name = "interop"

loinc = CrudResource(
    "loinc", LoincCode, views.LoincForm,
    roles=views.MANAGERS, title="LOINC catalogue", singular="LOINC code",
    columns=[("LOINC", "loinc_code", "mono"), ("Short name", "short_name", ""),
             ("Component", "component", ""), ("Property", "property", ""),
             ("System", "system", ""), ("Scale", "scale", ""), ("Status", "status", "")],
    search_fields=["loinc_code", "long_name", "short_name", "component"],
)

interfaces = CrudResource(
    "interface", InstrumentInterface, views.InterfaceForm,
    roles=views.MANAGERS_AND_INSTALLER, title="Instrument interfaces", singular="instrument interface",
    list_template="interop/interfaces.html",
    columns=[("Name", "name", ""), ("Protocol", "get_protocol_display", ""),
             ("Direction", "get_direction_display", ""), ("Host", "host", "mono"),
             ("Port", "port", ""), ("Last message", "last_message_at", "nowrap"),
             ("Stale", "is_stale", ""), ("Enabled", "enabled", "")],
    search_fields=["name", "host"],
)

icd10 = CrudResource(
    "icd10", Icd10Code, views.Icd10Form,
    roles=views.MANAGERS, title="ICD-10 diagnosis codes", singular="ICD-10 code",
    subtitle=(
        "Diagnosis codes attached to orders: clinical context for the rules "
        "engine, medical necessity for claims, and coded indications for audit."
    ),
    columns=[("Code", "code", "mono"), ("Description", "description", ""),
             ("Chapter", "chapter", ""), ("Billable", "billable", "")],
    search_fields=["code", "description", "chapter"],
    filter_fields={"billable": "billable"},
    deletable=True,
)


urlpatterns = [
    *loinc.urls("loinc/"),
    *icd10.urls("icd10/"),
    *interfaces.urls("interfaces/"),
    path("messages/", views.InstrumentMessageListView.as_view(), name="message_list"),
    path("queries/", views.HostQueryListView.as_view(), name="host_query_list"),
    path("fhir/DiagnosticReport/<str:pk>/", views.fhir_diagnostic_report, name="fhir_report"),
    path("hl7/oru/<str:pk>/", views.hl7_oru, name="hl7_oru"),
]
