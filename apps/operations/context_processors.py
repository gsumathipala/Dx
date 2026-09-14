"""Banner alerts shown across the application."""
from __future__ import annotations

from django.utils import timezone


def active_alerts(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}

    from apps.operations.models import SystemAlert

    alerts = (
        SystemAlert.objects.filter(active=True)
        .exclude(expires_at__lt=timezone.now())
        .exclude(read_by=user)
        .order_by("-created_at")[:5]
    )
    return {"dx_active_alerts": alerts}
