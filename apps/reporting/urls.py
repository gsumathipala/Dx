from django.urls import path

from apps.reporting import views

app_name = "reporting"

urlpatterns = [
    path("reports/", views.reports, name="reports"),
    path("reports/cumulative/", views.cumulative_report, name="cumulative"),
    path("reports/<str:pk>/", views.report_detail, name="report_detail"),
    path("email/", views.email_delivery, name="email_delivery"),

    path("documents/", views.DocumentListView.as_view(), name="documents"),
    path("documents/new/", views.DocumentCreateView.as_view(), name="document_create"),
    path("documents/<str:pk>/acknowledge/", views.acknowledge_document, name="document_acknowledge"),
    path("documents/<str:pk>/", views.DocumentUpdateView.as_view(), name="document_update"),

    path("requesters/", views.RequesterListView.as_view(), name="requester_list"),
    path("requesters/new/", views.RequesterCreateView.as_view(), name="requester_create"),
    path("requesters/<str:pk>/", views.RequesterUpdateView.as_view(), name="requester_update"),

    path("distribution/", views.DistributionRuleListView.as_view(), name="distribution_rules"),
    path("distribution/new/", views.DistributionRuleCreateView.as_view(), name="distribution_rule_create"),
    path("distribution/<str:pk>/", views.DistributionRuleUpdateView.as_view(), name="distribution_rule_update"),
]
