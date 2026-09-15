"""Authentication and user administration."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy

from apps.accounts.forms import CompetencyForm, DepartmentForm, UserForm
from apps.accounts.models import Department, UserCompetency
from apps.common.constants import MANAGEMENT_ROLES, Role
from apps.common.views import DxCreateView, DxDeleteView, DxListView, DxUpdateView

User = get_user_model()

ADMIN_ONLY = (Role.ADMIN,)
MANAGERS = tuple(MANAGEMENT_ROLES)


class DxLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_form_class(self):
        from apps.accounts.forms import DxLoginForm

        return DxLoginForm


class DxLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


# ── Users ────────────────────────────────────────────────────────────────────


# ── Departments ──────────────────────────────────────────────────────────────


# ── Competency (CLIA §493.1451) ──────────────────────────────────────────────
