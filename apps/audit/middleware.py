"""Binds the HTTP request to the audit context for the duration of the view."""
from __future__ import annotations

from apps.audit.context import context_from_request, reset_context, set_context


class AuditContextMiddleware:
    """Populate the ambient audit context from the incoming request.

    Placed after AuthenticationMiddleware so ``request.user`` is resolved.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_context(context_from_request(request))
        try:
            response = self.get_response(request)
        finally:
            reset_context(token)
        request_id = None
        try:
            request_id = context_from_request(request).request_id
        except Exception:  # pragma: no cover
            pass
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response
