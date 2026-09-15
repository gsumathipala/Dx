from django.urls import path

from apps.rules import views

app_name = "rules"

urlpatterns = [
    path("", views.RuleListView.as_view(), name="rule_list"),
    path("new/", views.RuleCreateView.as_view(), name="rule_create"),
    # Specific prefixes before "<pk>/", which would otherwise swallow them.
    path("log/", views.ExecutionListView.as_view(), name="execution_list"),
    path("log/<str:pk>/", views.execution_detail, name="execution_detail"),
    path("log/<str:pk>/override/", views.execution_override, name="execution_override"),
    path("<str:pk>/", views.rule_detail, name="rule_detail"),
    path("<str:pk>/edit/", views.RuleUpdateView.as_view(), name="rule_update"),
    path("<str:pk>/approve/", views.rule_approve, name="rule_approve"),
    path("<str:pk>/delete/", views.RuleDeleteView.as_view(), name="rule_delete"),
]
