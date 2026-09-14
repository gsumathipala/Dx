from django.urls import path

from apps.quality import views

app_name = "quality"

urlpatterns = [
    path("qc/", views.qc, name="qc"),
    path("qc/materials/", views.QcMaterialListView.as_view(), name="material_list"),
    path("qc/materials/new/", views.QcMaterialCreateView.as_view(), name="material_create"),
    path("qc/materials/<str:pk>/", views.QcMaterialUpdateView.as_view(), name="material_update"),
    path("qc/targets/", views.QcDefinitionListView.as_view(), name="definition_list"),
    path("qc/targets/new/", views.QcDefinitionCreateView.as_view(), name="definition_create"),
    path("qc/targets/<str:pk>/", views.QcDefinitionUpdateView.as_view(), name="definition_update"),

    path("equipment/", views.EquipmentListView.as_view(), name="equipment"),
    path("equipment/new/", views.EquipmentCreateView.as_view(), name="equipment_create"),
    path("equipment/log/", views.EquipmentLogListView.as_view(), name="equipment_log"),
    path("equipment/log/new/", views.EquipmentLogCreateView.as_view(), name="equipment_log_create"),
    path("equipment/<str:pk>/", views.EquipmentUpdateView.as_view(), name="equipment_update"),

    path("criteria/", views.RejectionCriterionListView.as_view(), name="criteria_list"),
    path("criteria/new/", views.RejectionCriterionCreateView.as_view(), name="criteria_create"),
    path("criteria/<str:pk>/", views.RejectionCriterionUpdateView.as_view(), name="criteria_update"),
]
