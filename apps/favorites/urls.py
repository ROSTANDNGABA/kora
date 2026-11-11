from django.urls import path

from . import views

app_name = "favorites"

urlpatterns = [
    path("favoris/", views.FavoriteListView.as_view(), name="list"),
    path("favoris/basculer/<int:provider_id>/", views.FavoriteToggleView.as_view(), name="toggle"),
    path("recherches/enregistrer/", views.SaveSearchView.as_view(), name="save_search"),
    path("recherches/<int:pk>/supprimer/", views.DeleteSearchView.as_view(), name="delete_search"),
]
