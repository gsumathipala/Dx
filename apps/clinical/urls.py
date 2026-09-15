from django.urls import path

from apps.clinical import forms as clinical_forms
from apps.clinical import views
from apps.clinical.models import (
    CalculatedTest, DeltaCheckFlag, DeltaCheckRule, DemographicReferenceRange,
    NotifiableCondition, ReflexRule,
)
from apps.common.views import CrudResource

app_name = "clinical"

delta_flags = CrudResource(
    "delta_flag", DeltaCheckFlag, None,
    roles=views.LAB_STAFF, title="Delta check flags",
    subtitle="Results that changed significantly from the patient's previous value.",
    columns=[("Flagged", "flagged_at", "nowrap"), ("Order", "order.accession_number", "mono"),
             ("Test", "test.code", "mono"), ("Previous", "previous_value", ""),
             ("Current", "current_value", ""), ("Change %", "delta_percent", ""),
             ("Acknowledged", "is_acknowledged", "")],
)

delta_rules = CrudResource(
    "delta_rule", DeltaCheckRule, clinical_forms.DeltaCheckRuleForm,
    roles=views.MANAGERS, title="Delta check rules", singular="delta check rule",
    columns=[("Test", "test_code", "mono"), ("Type", "get_delta_type_display", ""),
             ("Threshold", "threshold", ""), ("Direction", "direction", ""),
             ("Lookback (days)", "lookback_days", ""), ("Enabled", "enabled", "")],
    search_fields=["test_code", "test__name"],
    on_create=lambda view, form: setattr(form.instance, "created_by", view.request.user.username),
)

reflex_rules = CrudResource(
    "reflex_rule", ReflexRule, clinical_forms.ReflexRuleForm,
    roles=views.MANAGERS, title="Reflex testing rules", singular="reflex rule",
    columns=[("Name", "name", ""), ("Trigger", "trigger_test.code", "mono"),
             ("Condition", "operator", ""), ("Threshold", "threshold", ""),
             ("Adds", "add_test_code", "mono"), ("Enabled", "enabled", "")],
    search_fields=["name", "add_test_code"],
    on_create=lambda view, form: setattr(form.instance, "created_by", view.request.user.username),
)

ranges = CrudResource(
    "range", DemographicReferenceRange, clinical_forms.DemographicRangeForm,
    roles=views.MANAGERS, title="Demographic reference intervals", singular="reference interval",
    subtitle="Age, sex and pregnancy specific intervals, applied in preference to the test default.",
    columns=[("Test", "test_code", "mono"), ("Age from", "age_min", ""), ("Age to", "age_max", ""),
             ("Sex", "gender", ""), ("Pregnancy", "pregnancy", ""),
             ("Normal low", "low_normal", ""), ("Normal high", "high_normal", ""),
             ("Critical low", "low_critical", ""), ("Critical high", "high_critical", ""),
             ("Active", "active", "")],
    search_fields=["test_code"],
)

calculated = CrudResource(
    "calculated", CalculatedTest, clinical_forms.CalculatedTestForm,
    roles=views.MANAGERS, title="Calculated tests", singular="calculated test",
    subtitle="Derived analytes computed from other results rather than measured.",
    columns=[("Code", "test_code", "mono"), ("Name", "name", ""),
             ("Formula", "get_formula_display", ""), ("Inputs", "inputs", ""),
             ("Unit", "unit", ""), ("Active", "active", "")],
    search_fields=["test_code", "name"],
)

notifiable = CrudResource(
    "notifiable", NotifiableCondition, clinical_forms.NotifiableConditionForm,
    roles=views.ADMIN_ONLY, title="Notifiable conditions", singular="notifiable condition",
    subtitle="Conditions that must be reported to public health authorities.",
    columns=[("Condition", "name", ""), ("Organism", "organism", ""),
             ("Reporting body", "reporting_body", ""), ("Timeframe", "timeframe", ""),
             ("Active", "active", "")],
    search_fields=["name", "organism", "reporting_body"],
)

urlpatterns = [
    path("critical-values/", views.critical_values, name="critical_values"),
    path("critical-values/<str:pk>/acknowledge/", views.acknowledge_critical, name="acknowledge_critical"),
    path("epidemiology/", views.epidemiology, name="epidemiology"),
    path("epidemiology/<str:pk>/submit/", views.submit_epidemiology, name="submit_epidemiology"),

    *delta_flags.urls("delta-flags/"),
    *delta_rules.urls("rules/delta/"),
    *reflex_rules.urls("rules/reflex/"),
    *ranges.urls("ranges/"),
    *calculated.urls("calculated/"),
    *notifiable.urls("notifiable/"),
]
