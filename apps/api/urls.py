"""API routes, versioned in the path.

Versioning in the path rather than a header because it survives a browser, a
curl one-liner and a log line — and integration problems are diagnosed in all
three.
"""
from django.urls import path

from apps.api import views

app_name = "api"

urlpatterns = [
    path("", views.root, name="root"),

    path("tests/", views.tests, name="tests"),
    path("icd10/", views.icd10, name="icd10"),
    path("loinc/", views.loinc, name="loinc"),

    path("patients/", views.patients, name="patients"),
    path("patients/new/", views.patient_create, name="patient_create"),
    path("patients/<str:pk>/", views.patient_detail, name="patient_detail"),

    path("orders/", views.orders, name="orders"),
    path("orders/new/", views.order_create, name="order_create"),
    path("orders/<str:pk>/results/", views.order_results, name="order_results"),
    path("orders/<str:pk>/report/", views.order_report, name="order_report"),
    path("orders/<str:pk>/", views.order_detail, name="order_detail"),

    path("exceptions/", views.exceptions, name="exceptions"),

    path("webhooks/", views.webhooks, name="webhooks"),
    path("webhooks/<str:pk>/", views.webhook_detail, name="webhook_detail"),
]
