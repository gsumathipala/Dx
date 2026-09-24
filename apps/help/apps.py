"""The in-application help library, loaded from Markdown on disk."""
from django.apps import AppConfig


class HelpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.help"
    label = "help"
    verbose_name = "Help and reference"
