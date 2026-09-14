"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.interop.views import ingest
from apps.operations.views import healthz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    # Service-to-service endpoint: bearer-token authenticated, no session.
    path("api/middleware/ingest/", ingest, name="instrument_ingest"),
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
    path("", include("apps.operations.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
