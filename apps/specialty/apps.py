"""Histopathology and microbiology."""
from django.apps import AppConfig


class SpecialtyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.specialty"
    label = "specialty"
    verbose_name = "Specialty testing"
