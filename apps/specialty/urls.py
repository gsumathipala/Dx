from django.urls import path

from apps.specialty import views

app_name = "specialty"

urlpatterns = [
    path("histology/", views.histology, name="histology"),
    path("histology/blocks/", views.HistoBlockListView.as_view(), name="blocks"),
    path("histology/blocks/new/", views.HistoBlockCreateView.as_view(), name="block_create"),
    path("histology/blocks/<str:pk>/", views.HistoBlockUpdateView.as_view(), name="block_update"),
    path("histology/slides/", views.HistoSlideListView.as_view(), name="slides"),
    path("histology/slides/new/", views.HistoSlideCreateView.as_view(), name="slide_create"),
    path("histology/slides/<str:pk>/", views.HistoSlideUpdateView.as_view(), name="slide_update"),

    path("microbiology/", views.microbiology, name="microbiology"),
    path("microbiology/cultures/", views.CultureListView.as_view(), name="cultures"),
    path("microbiology/cultures/new/", views.CultureCreateView.as_view(), name="culture_create"),
    path("microbiology/cultures/<str:pk>/", views.CultureUpdateView.as_view(), name="culture_update"),
    path("microbiology/susceptibilities/", views.SusceptibilityListView.as_view(), name="susceptibilities"),
    path("microbiology/susceptibilities/new/", views.SusceptibilityCreateView.as_view(), name="susceptibility_create"),
    path("microbiology/antibiotics/", views.AntibioticListView.as_view(), name="antibiotics"),
    path("microbiology/antibiotics/new/", views.AntibioticCreateView.as_view(), name="antibiotic_create"),
    path("microbiology/antibiotics/<str:pk>/", views.AntibioticUpdateView.as_view(), name="antibiotic_update"),
]
