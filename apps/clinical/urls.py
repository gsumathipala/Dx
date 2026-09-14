from django.urls import path

from apps.clinical import views

app_name = "clinical"

urlpatterns = [
    path("critical-values/", views.critical_values, name="critical_values"),
    path("critical-values/<str:pk>/acknowledge/", views.acknowledge_critical, name="acknowledge_critical"),
    path("delta-flags/", views.DeltaFlagListView.as_view(), name="delta_flags"),

    path("epidemiology/", views.epidemiology, name="epidemiology"),
    path("epidemiology/<str:pk>/submit/", views.submit_epidemiology, name="submit_epidemiology"),

    path("rules/delta/", views.DeltaRuleListView.as_view(), name="delta_rules"),
    path("rules/delta/new/", views.DeltaRuleCreateView.as_view(), name="delta_rule_create"),
    path("rules/delta/<str:pk>/", views.DeltaRuleUpdateView.as_view(), name="delta_rule_update"),

    path("rules/reflex/", views.ReflexRuleListView.as_view(), name="reflex_rules"),
    path("rules/reflex/new/", views.ReflexRuleCreateView.as_view(), name="reflex_rule_create"),
    path("rules/reflex/<str:pk>/", views.ReflexRuleUpdateView.as_view(), name="reflex_rule_update"),

    path("ranges/", views.DemographicRangeListView.as_view(), name="demographic_ranges"),
    path("ranges/new/", views.DemographicRangeCreateView.as_view(), name="demographic_range_create"),
    path("ranges/<str:pk>/", views.DemographicRangeUpdateView.as_view(), name="demographic_range_update"),

    path("calculated/", views.CalculatedTestListView.as_view(), name="calculated_tests"),
    path("calculated/new/", views.CalculatedTestCreateView.as_view(), name="calculated_test_create"),
    path("calculated/<str:pk>/", views.CalculatedTestUpdateView.as_view(), name="calculated_test_update"),

    path("notifiable/", views.NotifiableConditionListView.as_view(), name="notifiable_list"),
    path("notifiable/new/", views.NotifiableConditionCreateView.as_view(), name="notifiable_create"),
    path("notifiable/<str:pk>/", views.NotifiableConditionUpdateView.as_view(), name="notifiable_update"),
]
