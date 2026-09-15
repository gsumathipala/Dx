from django.urls import path

from apps.common.views import CrudResource
from apps.compliance import forms as compliance_forms
from apps.compliance import subject_views, views
from apps.compliance.models import (
    ChangeControl, CorrectiveAction, DisclosureAccounting, MethodValidation,
    PHIAccessLog, ProficiencyResult, ProficiencySurvey, RetentionSchedule,
    RiskAssessment, TrainingRecord,
)

app_name = "compliance"

capa = CrudResource(
    "capa", CorrectiveAction, compliance_forms.CorrectiveActionForm,
    roles=views.LAB_STAFF, title="Corrective and preventive actions", singular="nonconformance",
    subtitle="Nonconformance management — ISO 15189 §8.7 / CAP",
    columns=[("Reference", "reference", "mono"), ("Title", "title", ""),
             ("Category", "get_category_display", ""), ("Severity", "severity", ""),
             ("Status", "status", ""), ("Raised", "raised_at", "nowrap"),
             ("Due", "due_date", "nowrap")],
    search_fields=["reference", "title", "description"],
    filter_fields={"status": "status", "category": "category"},
    on_create=views.stamp_capa_creation,
    on_update=views.stamp_capa_closure,
)

pt_surveys = CrudResource(
    "pt", ProficiencySurvey, compliance_forms.ProficiencySurveyForm,
    roles=views.LAB_STAFF, title="Proficiency testing", singular="proficiency survey",
    subtitle="External quality assessment — CLIA 42 CFR §493.801",
    columns=[("Provider", "provider", ""), ("Survey", "survey_code", "mono"),
             ("Year", "year", ""), ("Event", "event", ""), ("Discipline", "discipline", ""),
             ("Due", "due_date", "nowrap"), ("Submitted", "submitted_date", "nowrap"),
             ("Attested", "attestation_signed", "")],
    search_fields=["provider", "survey_code", "discipline"],
)

pt_results = CrudResource(
    "pt_result", ProficiencyResult, compliance_forms.ProficiencyResultForm,
    roles=views.LAB_STAFF, title="Proficiency results", singular="proficiency result",
    columns=[("Survey", "survey", ""), ("Analyte", "analyte", ""),
             ("Sample", "sample_id", "mono"), ("Reported", "reported_value", ""),
             ("Target", "target_value", ""), ("Z-score", "z_score", ""),
             ("Grade", "grade", ""), ("CAPA required", "requires_corrective_action", "")],
    search_fields=["analyte", "sample_id"],
)

validations = CrudResource(
    "validation", MethodValidation, compliance_forms.MethodValidationForm,
    roles=views.MANAGERS, title="Method validation", singular="method validation",
    subtitle="Performance specification verification — CLIA 42 CFR §493.1253",
    columns=[("Test", "test.code", "mono"), ("Kind", "get_kind_display", ""),
             ("Instrument", "instrument.name", ""), ("Started", "started_on", "nowrap"),
             ("Completed", "completed_on", "nowrap"), ("All elements", "all_elements_verified", ""),
             ("Status", "status", "")],
    search_fields=["test__code", "test__name", "performed_by"],
    on_update=views.stamp_validation_approval,
)

risks = CrudResource(
    "risk", RiskAssessment, compliance_forms.RiskAssessmentForm,
    roles=views.MANAGERS, title="Risk register", singular="risk",
    subtitle="Risk management — ISO 15189:2022 §8.5",
    columns=[("Reference", "reference", "mono"), ("Title", "title", ""),
             ("Process", "process_area", ""), ("Score", "risk_score", ""),
             ("Residual", "residual_score", ""), ("Rating", "rating", ""),
             ("Status", "status", ""), ("Next review", "next_review", "nowrap")],
    search_fields=["reference", "title", "process_area"],
    on_create=views.stamp_risk_reference,
)

changes = CrudResource(
    "change", ChangeControl, compliance_forms.ChangeControlForm,
    roles=views.MANAGERS_AND_INSTALLER, title="Change control", singular="change request",
    subtitle="System and method changes — 21 CFR Part 11 §11.10(a)",
    columns=[("Reference", "reference", "mono"), ("Title", "title", ""),
             ("Type", "change_type", ""), ("Requested", "requested_at", "nowrap"),
             ("Status", "status", "")],
    search_fields=["reference", "title", "description"],
    on_create=views.stamp_change_reference,
    on_update=views.stamp_change_approval,
)

training = CrudResource(
    "training", TrainingRecord, compliance_forms.TrainingRecordForm,
    roles=None, title="Training records", singular="training record",
    subtitle="CLIA 42 CFR §493.1451(b)(8)",
    columns=[("Staff member", "user.name", ""), ("Topic", "topic", ""),
             ("Trainer", "trainer", ""), ("Completed", "completed_on", "nowrap"),
             ("Expires", "expires_on", "nowrap"), ("Status", "status", "")],
    search_fields=["user__name", "topic", "trainer"],
)

retention = CrudResource(
    "retention", RetentionSchedule, compliance_forms.RetentionScheduleForm,
    roles=views.MANAGERS, title="Record retention schedule", singular="retention rule",
    subtitle="Minimum retention periods — CLIA 42 CFR §493.1105",
    columns=[("Record class", "get_record_class_display", ""),
             ("Years", "retention_years", ""), ("Basis", "citation", "muted"),
             ("Destruction", "destruction_method", ""), ("Active", "active", "")],
)

phi_access = CrudResource(
    "phi_access", PHIAccessLog, None,
    roles=views.ADMIN_ONLY, title="PHI access log",
    subtitle="Who viewed identifiable patient information — HIPAA §164.312(b)",
    columns=[("When", "timestamp", "nowrap"), ("User", "username", ""),
             ("Patient MRN", "patient_mrn", "mono"), ("Path", "path", "muted"),
             ("Purpose", "purpose", ""), ("Emergency override", "break_the_glass", ""),
             ("Address", "ip_address", "mono")],
    search_fields=["username", "patient_mrn", "path"],
)

disclosures = CrudResource(
    "disclosure", DisclosureAccounting, None,
    roles=views.ADMIN_ONLY, title="Disclosure accounting",
    subtitle=("Disclosures of protected health information — HIPAA §164.528. "
              "A patient may request an accounting covering the previous six years."),
    columns=[("When", "disclosed_at", "nowrap"), ("Patient", "patient.mrn", "mono"),
             ("Recipient", "recipient_name", ""), ("Purpose", "get_purpose_display", ""),
             ("Method", "method", ""), ("Authorised", "authorised_by_patient", ""),
             ("By", "disclosed_by", "")],
    search_fields=["recipient_name", "patient__mrn", "description"],
)

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("password/", views.password_change, name="password_change"),

    *capa.urls("capa/"),
    # Results before surveys: "proficiency/<pk>/" would otherwise shadow them.
    *pt_results.urls("proficiency/results/"),
    *pt_surveys.urls("proficiency/"),
    *validations.urls("validation/"),
    *risks.urls("risk/"),
    *changes.urls("change/"),
    *training.urls("training/"),
    *retention.urls("retention/"),
    *phi_access.urls("phi-access/"),
    *disclosures.urls("disclosures/"),

    # GDPR data subject requests. Specific paths before "<pk>/".
    path("subject-requests/", subject_views.SubjectRequestListView.as_view(),
         name="subject_request_list"),
    path("subject-requests/new/", subject_views.subject_request_create,
         name="subject_request_create"),
    path("subject-requests/<str:pk>/", subject_views.subject_request_detail,
         name="subject_request_detail"),
    path("subject-requests/<str:pk>/verify/", subject_views.subject_request_verify,
         name="subject_request_verify"),
    path("subject-requests/<str:pk>/extend/", subject_views.subject_request_extend,
         name="subject_request_extend"),
    path("subject-requests/<str:pk>/export/", subject_views.subject_request_export,
         name="subject_request_export"),
    path("subject-requests/<str:pk>/download/", subject_views.subject_request_download,
         name="subject_request_download"),
    path("subject-requests/<str:pk>/erase/", subject_views.subject_request_erase,
         name="subject_request_erase"),
    path("subject-requests/<str:pk>/restrict/", subject_views.subject_request_restrict,
         name="subject_request_restrict"),
]
