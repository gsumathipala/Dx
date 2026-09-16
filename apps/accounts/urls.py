from django.urls import path

from apps.accounts import forms as account_forms
from apps.accounts import lock_views, mfa_views, sso_views, views
from apps.accounts.models import Department, UserCompetency
from apps.common.views import CrudResource
from django.contrib.auth import get_user_model

app_name = "accounts"

User = get_user_model()

users = CrudResource(
    "user", User, account_forms.UserForm,
    roles=views.SYSTEM, title="User management", singular="user",
    subtitle="Unique named accounts — 21 CFR Part 11 §11.10(d). Shared logins are not permitted.",
    columns=[("Username", "username", "mono"), ("Name", "name", ""),
             ("Role", "get_role_display", ""), ("Department", "department_name", ""),
             ("Email", "email", ""), ("Active", "is_active", "")],
    search_fields=["username", "name", "email"],
    app_namespace="accounts",
    list_template="accounts/user_list.html",
)

departments = CrudResource(
    "department", Department, account_forms.DepartmentForm,
    roles=views.SYSTEM, title="Departments", singular="department",
    columns=[("Name", "name", ""), ("Code", "code", "mono"), ("Type", "type", ""),
             ("Enabled", "enabled", "")],
    search_fields=["name", "code"],
)

competency = CrudResource(
    "competency", UserCompetency, account_forms.CompetencyForm,
    roles=views.MANAGERS, title="User competency", singular="competency record",
    subtitle=("CLIA 42 CFR §493.1451(b)(8) — staff may not report results for tests "
              "they are not currently assessed as competent to perform."),
    list_template="accounts/competency_list.html",
    columns=[("Staff member", "user.name", ""), ("Test", "test.code", "mono"),
             ("Category", "category", ""), ("Assessed", "competency_date", "nowrap"),
             ("Expires", "expiry_date", "nowrap"), ("Status", "effective_status", "")],
    search_fields=["user__username", "user__name", "category"],
)

urlpatterns = [
    path("login/", views.DxLoginView.as_view(), name="login"),
    path("logout/", views.DxLogoutView.as_view(), name="logout"),

    # Single sign-on.
    path("sso/", sso_views.begin, name="sso_begin"),
    path("sso/callback/", sso_views.callback, name="sso_callback"),

    # Two-factor authentication.
    path("mfa/", mfa_views.status, name="mfa_status"),
    path("mfa/challenge/", mfa_views.challenge, name="mfa_challenge"),
    path("mfa/setup/", mfa_views.setup, name="mfa_setup"),
    path("mfa/disable/", mfa_views.disable, name="mfa_disable"),
    path("mfa/recovery/", mfa_views.regenerate_recovery_codes, name="mfa_recovery"),

    # Record locking: two endpoints the open page calls, and the screen a
    # manager uses to break a lock somebody left behind.
    path("locks/", lock_views.lock_list, name="lock_list"),
    path("locks/heartbeat/", lock_views.heartbeat, name="lock_heartbeat"),
    path("locks/release/", lock_views.release, name="lock_release"),
    path("locks/<str:pk>/break/", lock_views.lock_break, name="lock_break"),

    # Before the users resource, whose `<pk>/` pattern would shadow these.
    path("users/<str:pk>/reset-password/", views.reset_password, name="user_reset_password"),
    path("users/<str:pk>/toggle-active/", views.toggle_active, name="user_toggle_active"),
    path("users/<str:pk>/delete/", views.delete_user, name="user_delete"),
    *users.urls("users/"),
    *departments.urls("departments/"),
    *competency.urls("competency/"),
]
