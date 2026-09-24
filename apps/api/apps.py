"""The public JSON API, its client credentials and outbound webhooks."""
from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "apps.api"
    label = "api"
    verbose_name = "Public API"

    def ready(self):
        # Registers the deployment checks so they run on every manage.py check.
        from apps.api import checks  # noqa: F401
