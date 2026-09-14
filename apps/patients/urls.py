from django.urls import path

from apps.patients import views

app_name = "patients"

urlpatterns = [
    path("", views.PatientListView.as_view(), name="list"),
    path("admin/", views.PatientAdminListView.as_view(), name="admin_list"),
    path("new/", views.PatientCreateView.as_view(), name="create"),
    path("<str:pk>/", views.patient_detail, name="detail"),
    path("<str:pk>/edit/", views.PatientUpdateView.as_view(), name="update"),
    path("<str:pk>/trend/", views.patient_trend, name="trend"),
]
