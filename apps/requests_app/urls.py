from django.urls import path

from . import views

app_name = "requests_app"

urlpatterns = [
    path("artisans/<slug:slug>/devis/", views.RequestCreateView.as_view(), name="create"),
    path("mes-demandes/", views.MyRequestsView.as_view(), name="list"),
    path("mes-demandes/<int:pk>/", views.RequestDetailView.as_view(), name="detail"),
    path("mes-demandes/<int:pk>/annuler/", views.CancelRequestView.as_view(), name="cancel"),
    path("devis/<int:pk>/accepter/", views.AcceptQuoteView.as_view(), name="quote_accept"),
    path("devis/<int:pk>/refuser/", views.DeclineQuoteView.as_view(), name="quote_decline"),
]
