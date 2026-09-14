"""Authentication gate."""
from __future__ import annotations

import re

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

#: Views reachable without a session. Everything else requires authentication,
#: which is the safe default for a system holding patient data — the legacy
#: implementation relied on each route remembering to check, and one did not.
PUBLIC_PATH_PATTERNS = [
    re.compile(r"^/accounts/login/?$"),
    re.compile(r"^/accounts/logout/?$"),
    re.compile(r"^/healthz/?$"),
    re.compile(r"^/static/"),
    re.compile(r"^/media/"),
    # The instrument interface authenticates with a bearer token instead.
    re.compile(r"^/api/middleware/ingest/?$"),
]


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return self.get_response(request)

        path = request.path
        if any(pattern.match(path) for pattern in PUBLIC_PATH_PATTERNS):
            return self.get_response(request)

        if path.startswith("/api/"):
            from django.http import JsonResponse

            return JsonResponse({"error": "Unauthorized"}, status=401)

        login_url = reverse(settings.LOGIN_URL) if ":" in str(settings.LOGIN_URL) else settings.LOGIN_URL
        return redirect(f"{login_url}?next={path}")
