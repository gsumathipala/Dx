from django.urls import path

from apps.compliance import views

app_name = "compliance"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("password/", views.password_change, name="password_change"),

    path("capa/", views.CapaListView.as_view(), name="capa_list"),
    path("capa/new/", views.CapaCreateView.as_view(), name="capa_create"),
    path("capa/<str:pk>/", views.CapaUpdateView.as_view(), name="capa_update"),

    path("proficiency/", views.ProficiencyListView.as_view(), name="pt_list"),
    path("proficiency/new/", views.ProficiencyCreateView.as_view(), name="pt_create"),
    path("proficiency/results/", views.ProficiencyResultListView.as_view(), name="pt_result_list"),
    path("proficiency/results/new/", views.ProficiencyResultCreateView.as_view(), name="pt_result_create"),
    path("proficiency/<str:pk>/", views.ProficiencyUpdateView.as_view(), name="pt_update"),

    path("validation/", views.ValidationListView.as_view(), name="validation_list"),
    path("validation/new/", views.ValidationCreateView.as_view(), name="validation_create"),
    path("validation/<str:pk>/", views.ValidationUpdateView.as_view(), name="validation_update"),

    path("risk/", views.RiskListView.as_view(), name="risk_list"),
    path("risk/new/", views.RiskCreateView.as_view(), name="risk_create"),
    path("risk/<str:pk>/", views.RiskUpdateView.as_view(), name="risk_update"),

    path("change/", views.ChangeListView.as_view(), name="change_list"),
    path("change/new/", views.ChangeCreateView.as_view(), name="change_create"),
    path("change/<str:pk>/", views.ChangeUpdateView.as_view(), name="change_update"),

    path("training/", views.TrainingListView.as_view(), name="training_list"),
    path("training/new/", views.TrainingCreateView.as_view(), name="training_create"),
    path("training/<str:pk>/", views.TrainingUpdateView.as_view(), name="training_update"),

    path("retention/", views.RetentionScheduleListView.as_view(), name="retention_schedule"),
    path("retention/<str:pk>/", views.RetentionScheduleUpdateView.as_view(), name="retention_update"),

    path("phi-access/", views.PHIAccessLogView.as_view(), name="phi_access_log"),
    path("disclosures/", views.DisclosureListView.as_view(), name="disclosure_list"),
]
