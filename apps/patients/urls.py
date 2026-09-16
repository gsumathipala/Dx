from django.urls import path

from apps.common.views import CrudResource
from apps.patients import views
from apps.patients.forms import PatientForm
from apps.patients.models import Patient

app_name = "patients"

PATIENT_COLUMNS = [
    ("MRN", "mrn", "mono"), ("Name", "full_name", ""),
    ("Date of birth", "dob", "nowrap"), ("Age", "age_display", ""),
    ("Sex", "get_gender_display", ""), ("Phone", "phone", ""),
]

patients = CrudResource(
    "patient", Patient, PatientForm,
    roles=None, title="Patients", singular="patient",
    columns=PATIENT_COLUMNS,
    search_fields=["first_name", "last_name", "mrn", "phone", "email"],
    lock_entity_type="patients.Patient",
)

# Same list reached from the administration menu; the labelling differs so a
# manager knows corrections here are attributed to them.
admin_patients = CrudResource(
    "patient_admin", Patient, None,
    roles=views.MANAGERS, title="Patient data administration",
    subtitle="Demographic corrections are recorded against your account in the audit trail.",
    columns=PATIENT_COLUMNS,
    search_fields=["first_name", "last_name", "mrn"],
)

# Patients own `<pk>/` for the consolidated record, so the generated views are
# mounted on explicit paths rather than the factory's default layout.
urlpatterns = [
    path("", patients.list_view().as_view(), name="patient_list"),
    path("new/", patients.create_view().as_view(), name="patient_create"),
    path("admin/", admin_patients.list_view().as_view(), name="patient_admin_list"),
    path("<str:pk>/edit/", patients.update_view().as_view(), name="patient_update"),
    path("<str:pk>/trend/", views.patient_trend, name="trend"),
    path("<str:pk>/", views.patient_detail, name="detail"),
]
