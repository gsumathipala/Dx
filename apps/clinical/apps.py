"""The clinical decision engine: delta checks, critical values, reflex testing."""
from django.apps import AppConfig


class ClinicalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.clinical"
    label = "clinical"
    verbose_name = "Clinical engine"
