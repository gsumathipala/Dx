"""URL routes for the in-application help library."""
from django.urls import path

from apps.help import views

app_name = "help"

urlpatterns = [
    path("", views.index, name="index"),
    path("search/", views.search, name="search"),
    path("go/", views.contextual, name="contextual"),
    path("<str:section_slug>/", views.section, name="section"),
    path("<str:section_slug>/<str:topic_slug>/", views.topic, name="topic"),
]
