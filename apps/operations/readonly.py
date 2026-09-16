"""Read-only mode.

Used during recovery: the system is up and reachable and must not be written
to until somebody has confirmed the database is intact. A restore racing
against live traffic is how a laboratory ends up with a chain that will not
verify and no way to tell which results are real.

Everything unsafe is refused, with one deliberate exception — signing out.
Trapping people in a session they cannot leave achieves nothing and makes the
mode feel like a fault rather than a control.
"""
from __future__ import annotations

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

#: Paths that must keep working while the system is read-only.
ALWAYS_ALLOWED = (
    "/accounts/logout/",
    "/accounts/login/",
    "/healthz",
    "/metrics",
)


class ReadOnlyModeMiddleware:
    """Refuse writes while the system is in read-only mode.

    The check is one indexed lookup per unsafe request, and only for unsafe
    requests — a read costs nothing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in SAFE_METHODS:
            return self.get_response(request)
        if request.path.startswith(ALWAYS_ALLOWED):
            return self.get_response(request)

        from apps.operations.continuity import read_only_reason

        reason = read_only_reason()
        if reason is None:
            return self.get_response(request)

        message = (
            "The system is in read-only mode and nothing can be saved. "
            f"Reason given: {reason}. "
            "Record results on paper against the current downtime record; "
            "an administrator lifts read-only mode from the maintenance screen."
        )

        if request.path.startswith("/api/"):
            return JsonResponse(
                {"error": {"code": "read_only", "message": message}}, status=503
            )

        messages.error(request, message)
        return redirect(request.META.get("HTTP_REFERER") or "/")
