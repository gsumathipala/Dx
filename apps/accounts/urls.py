from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.DxLoginView.as_view(), name="login"),
    path("logout/", views.DxLogoutView.as_view(), name="logout"),

    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/new/", views.UserCreateView.as_view(), name="user_create"),
    path("users/<str:pk>/", views.UserUpdateView.as_view(), name="user_update"),

    path("departments/", views.DepartmentListView.as_view(), name="department_list"),
    path("departments/new/", views.DepartmentCreateView.as_view(), name="department_create"),
    path("departments/<str:pk>/", views.DepartmentUpdateView.as_view(), name="department_update"),

    path("competency/", views.CompetencyListView.as_view(), name="competency_list"),
    path("competency/new/", views.CompetencyCreateView.as_view(), name="competency_create"),
    path("competency/<str:pk>/", views.CompetencyUpdateView.as_view(), name="competency_update"),
]
