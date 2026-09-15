from django.urls import path

from apps.common.views import CrudResource
from apps.interop import views
from apps.interop.models import InstrumentInterface, InstrumentMessage, LoincCode

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



urlpatterns = [
    *loinc.urls("loinc/"),
    *interfaces.urls("interfaces/"),
    path("messages/", views.InstrumentMessageListView.as_view(), name="message_list"),
    path("fhir/DiagnosticReport/<str:pk>/", views.fhir_diagnostic_report, name="fhir_report"),
    path("hl7/oru/<str:pk>/", views.hl7_oru, name="hl7_oru"),
]
