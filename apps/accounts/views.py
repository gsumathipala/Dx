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


class UserListView(DxListView):
    model = User
    required_roles = ADMIN_ONLY
    page_title = "User management"
    page_subtitle = "Unique named accounts — 21 CFR Part 11 §11.10(d). Shared logins are not permitted."
    search_fields = ["username", "name", "email"]
    columns = [
        ("Username", "username", "mono"), ("Name", "name", ""),
        ("Role", "get_role_display", ""), ("Department", "department_name", ""),
        ("Email", "email", ""), ("Active", "is_active", ""),
    ]
    create_url_name = "accounts:user_create"
    update_url_name = "accounts:user_update"


class UserCreateView(DxCreateView):
    model = User
    form_class = UserForm
    required_roles = ADMIN_ONLY
    page_title = "user"
    success_url = reverse_lazy("accounts:user_list")


class UserUpdateView(DxUpdateView):
    model = User
    form_class = UserForm
    required_roles = ADMIN_ONLY
    page_title = "user"
    success_url = reverse_lazy("accounts:user_list")


# ── Departments ──────────────────────────────────────────────────────────────


class DepartmentListView(DxListView):
    model = Department
    required_roles = ADMIN_ONLY
    page_title = "Departments"
    search_fields = ["name", "code"]
    columns = [
        ("Name", "name", ""), ("Code", "code", "mono"), ("Type", "type", ""),
        ("Enabled", "enabled", ""),
    ]
    create_url_name = "accounts:department_create"
    update_url_name = "accounts:department_update"


class DepartmentCreateView(DxCreateView):
    model = Department
    form_class = DepartmentForm
    required_roles = ADMIN_ONLY
    page_title = "department"
    success_url = reverse_lazy("accounts:department_list")


class DepartmentUpdateView(DxUpdateView):
    model = Department
    form_class = DepartmentForm
    required_roles = ADMIN_ONLY
    page_title = "department"
    success_url = reverse_lazy("accounts:department_list")


# ── Competency (CLIA §493.1451) ──────────────────────────────────────────────


class CompetencyListView(DxListView):
    model = UserCompetency
    required_roles = MANAGERS
    template_name = "accounts/competency_list.html"
    page_title = "User competency"
    page_subtitle = (
        "CLIA 42 CFR §493.1451(b)(8) — staff may not report results for tests "
        "they are not currently assessed as competent to perform."
    )
    search_fields = ["user__username", "user__name", "category"]
    columns = [
        ("Staff member", "user.name", ""), ("Test", "test.code", "mono"),
        ("Category", "category", ""), ("Assessed", "competency_date", "nowrap"),
        ("Expires", "expiry_date", "nowrap"), ("Status", "effective_status", ""),
    ]
    create_url_name = "accounts:competency_create"
    update_url_name = "accounts:competency_update"

    def get_queryset(self):
        return super().get_queryset().select_related("user", "test")


class CompetencyCreateView(DxCreateView):
    model = UserCompetency
    form_class = CompetencyForm
    required_roles = MANAGERS
    page_title = "competency record"
    success_url = reverse_lazy("accounts:competency_list")


class CompetencyUpdateView(DxUpdateView):
    model = UserCompetency
    form_class = CompetencyForm
    required_roles = MANAGERS
    page_title = "competency record"
    success_url = reverse_lazy("accounts:competency_list")
