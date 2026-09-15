from django.urls import path

from apps.accounts import forms as account_forms
from apps.accounts import views
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

    # Before the users resource, whose `<pk>/` pattern would shadow these.
    path("users/<str:pk>/reset-password/", views.reset_password, name="user_reset_password"),
    path("users/<str:pk>/toggle-active/", views.toggle_active, name="user_toggle_active"),
    path("users/<str:pk>/delete/", views.delete_user, name="user_delete"),
    *users.urls("users/"),
    *departments.urls("departments/"),
    *competency.urls("competency/"),
]
