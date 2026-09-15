"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.interop.views import host_query, ingest, inbound_hl7
from apps.operations.views import healthz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    # Service-to-service endpoints: bearer-token authenticated, no session.
    # These serve the instrument middleware and the hospital's integration
    # engine, neither of which has a browser session to present.
    path("api/middleware/ingest/", ingest, name="instrument_ingest"),
    path("api/middleware/query/", host_query, name="instrument_host_query"),
    path("api/middleware/hl7/", inbound_hl7, name="inbound_hl7"),
    # The public, client-credentialed API.
    path("api/v1/", include("apps.api.urls")),
    path("django-admin/", admin.site.urls),

    path("accounts/", include("apps.accounts.urls")),
    path("patients/", include("apps.patients.urls")),
    path("", include("apps.laboratory.urls")),
    path("clinical/", include("apps.clinical.urls")),
    path("quality/", include("apps.quality.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("specialty/", include("apps.specialty.urls")),
    path("billing/", include("apps.billing.urls")),
    path("reporting/", include("apps.reporting.urls")),
    path("interop/", include("apps.interop.urls")),
    path("audit/", include("apps.audit.urls")),
    path("compliance/", include("apps.compliance.urls")),
    path("rules/", include("apps.rules.urls")),
    path("integrations/", include("apps.api.manage_urls")),
    path("help/", include("apps.help.urls")),
    path("", include("apps.operations.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
