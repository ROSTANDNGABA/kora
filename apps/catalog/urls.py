from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("recherche/", views.SearchView.as_view(), name="search"),
    path("categorie/<slug:slug>/", views.CategoryView.as_view(), name="category"),
]
