"""HL7, FHIR, LOINC, ICD-10 and instrument interfacing."""
from django.apps import AppConfig


class InteropConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.interop"
    label = "interop"
    verbose_name = "Interoperability"
