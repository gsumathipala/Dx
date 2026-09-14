from django.urls import path

from apps.laboratory import views

app_name = "laboratory"

urlpatterns = [
    path("accessioning/", views.accessioning, name="accessioning"),
    path("receiving/", views.receiving, name="receiving"),

    path("results/", views.results_worklist, name="results"),
    path("results/<str:pk>/", views.result_entry, name="result_entry"),

    path("phlebotomy/", views.PhlebotomyListView.as_view(), name="phlebotomy"),
    path("phlebotomy/new/", views.PhlebotomyCreateView.as_view(), name="phlebotomy_create"),
    path("phlebotomy/<str:pk>/", views.PhlebotomyUpdateView.as_view(), name="phlebotomy_update"),

    path("config/tests/", views.TestListView.as_view(), name="test_list"),
    path("config/tests/new/", views.TestCreateView.as_view(), name="test_create"),
    path("config/tests/<str:pk>/", views.TestUpdateView.as_view(), name="test_update"),

    path("config/queues/", views.QueueListView.as_view(), name="queue_list"),
    path("config/queues/new/", views.QueueCreateView.as_view(), name="queue_create"),
    path("config/queues/<str:pk>/", views.QueueUpdateView.as_view(), name="queue_update"),

    path("config/retention/", views.RetentionListView.as_view(), name="retention_list"),
    path("config/retention/new/", views.RetentionCreateView.as_view(), name="retention_create"),
    path("config/retention/<str:pk>/", views.RetentionUpdateView.as_view(), name="retention_update"),
]
