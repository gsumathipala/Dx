from django.urls import path

from apps.interop import views

app_name = "interop"

urlpatterns = [
    path("loinc/", views.LoincListView.as_view(), name="loinc_list"),
    path("loinc/new/", views.LoincCreateView.as_view(), name="loinc_create"),
    path("loinc/<str:pk>/", views.LoincUpdateView.as_view(), name="loinc_update"),

    path("interfaces/", views.InterfaceListView.as_view(), name="interface_list"),
    path("interfaces/new/", views.InterfaceCreateView.as_view(), name="interface_create"),
    path("interfaces/messages/", views.MessageLogView.as_view(), name="message_log"),
    path("interfaces/<str:pk>/", views.InterfaceUpdateView.as_view(), name="interface_update"),

    path("fhir/DiagnosticReport/<str:pk>/", views.fhir_diagnostic_report, name="fhir_report"),
    path("hl7/oru/<str:pk>/", views.hl7_oru, name="hl7_oru"),
]
