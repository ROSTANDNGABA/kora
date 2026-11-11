from django.urls import path

from . import views

app_name = "dashboard_provider"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("profil/", views.ProfileView.as_view(), name="profile"),
    path("portfolio/", views.PortfolioView.as_view(), name="portfolio"),
    path("portfolio/<int:pk>/legende/", views.PortfolioCaptionView.as_view(), name="portfolio_caption"),
    path("portfolio/<int:pk>/deplacer/<str:direction>/", views.PortfolioMoveView.as_view(), name="portfolio_move"),
    path("portfolio/<int:pk>/supprimer/", views.PortfolioDeleteView.as_view(), name="portfolio_delete"),
    path("services/", views.ServiceListView.as_view(), name="services"),
    path("services/nouveau/", views.ServiceFormView.as_view(), name="service_new"),
    path("services/<int:pk>/modifier/", views.ServiceFormView.as_view(), name="service_edit"),
    path("services/<int:pk>/supprimer/", views.ServiceDeleteView.as_view(), name="service_delete"),
    path("services/<int:pk>/afficher/", views.ServiceToggleView.as_view(), name="service_toggle"),
    path("disponibilites/", views.AvailabilityView.as_view(), name="availability"),
    path("demandes/", views.RequestListView.as_view(), name="requests"),
    path("demandes/<int:pk>/", views.RequestDetailView.as_view(), name="request_detail"),
    path("demandes/<int:pk>/accepter/", views.RequestAcceptView.as_view(), name="request_accept"),
    path("demandes/<int:pk>/refuser/", views.RequestRefuseView.as_view(), name="request_refuse"),
    path("demandes/<int:pk>/devis/", views.RequestQuoteView.as_view(), name="request_quote"),
    path("demandes/<int:pk>/demarrer/", views.RequestStartView.as_view(), name="request_start"),
    path("demandes/<int:pk>/terminer/", views.RequestFinishView.as_view(), name="request_finish"),
    path("avis/", views.ReviewListView.as_view(), name="reviews"),
    path("avis/<int:pk>/repondre/", views.ReviewReplyView.as_view(), name="review_reply"),
    path("statistiques/", views.StatsView.as_view(), name="stats"),
    path("verification/", views.VerificationView.as_view(), name="verification"),
    path("parametres/", views.SettingsView.as_view(), name="settings"),
]
