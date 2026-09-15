from django.urls import path

from apps.common.views import CrudResource
from apps.reporting import views
from apps.reporting.models import ControlledDocument, DistributionRule, Requester

app_name = "reporting"

documents = CrudResource(
    "document", ControlledDocument, views.ControlledDocumentForm,
    roles=views.MANAGERS, title="Controlled documents", singular="controlled document",
    subtitle="SOPs, policies and manuals under version control — ISO 15189 §8.3",
    list_template="reporting/documents.html",
    columns=[("Number", "document_number", "mono"), ("Title", "title", ""),
             ("Category", "category", ""), ("Version", "version", ""),
             ("Status", "status", ""), ("Effective", "effective_date", "nowrap"),
             ("Review due", "review_due", "nowrap"), ("Overdue", "review_overdue", "")],
    search_fields=["title", "document_number"],
    filter_fields={"category": "category", "status": "status"},
    on_create=lambda view, form: setattr(form.instance, "uploaded_by", view.request.user.username),
    on_update=views.stamp_document_approval,
)

requesters = CrudResource(
    "requester", Requester, views.RequesterForm,
    roles=views.MANAGERS, title="Requester registry", singular="requester",
    columns=[("Name", "name", ""), ("Type", "type", ""), ("Contact", "contact_name", ""),
             ("Email", "email", ""), ("Phone", "phone", ""),
             ("Delivery", "delivery_preference", ""), ("Active", "active", "")],
    search_fields=["name", "contact_name", "email"],
)

distribution = CrudResource(
    "distribution", DistributionRule, views.DistributionRuleForm,
    roles=views.MANAGERS, title="Distribution rules", singular="distribution rule",
    columns=[("Requester", "requester.name", ""), ("Test", "test.code", "mono"),
             ("Method", "method", ""), ("Destination", "destination", ""),
             ("Auto release", "auto_release", ""), ("Active", "active", "")],
)

urlpatterns = [
    path("reports/", views.reports, name="reports"),
    path("reports/cumulative/", views.cumulative_report, name="cumulative"),
    path("reports/<str:pk>/amend/", views.amend_report_view, name="amend"),
    path("reports/<str:pk>/", views.report_detail, name="report_detail"),
    path("email/", views.email_delivery, name="email_delivery"),

    # Before the documents resource, whose `<pk>/` pattern would shadow it.
    path("documents/<str:pk>/acknowledge/", views.acknowledge_document, name="document_acknowledge"),
    *documents.urls("documents/"),
    *requesters.urls("requesters/"),
    *distribution.urls("distribution/"),
]
