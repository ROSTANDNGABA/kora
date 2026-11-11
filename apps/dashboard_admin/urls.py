from django.urls import path

from . import views_catalog as cat
from . import views_content as cnt
from . import views_core as core
from . import views_moderation as mod
from . import views_system as sys
from . import views_users as usr

app_name = "dashboard_admin"

urlpatterns = [
    path("", core.HomeView.as_view(), name="home"),
    path("recherche/", core.SearchView.as_view(), name="search"),
    # Clients
    path("clients/", usr.ClientListView.as_view(), name="clients"),
    path("clients/<int:pk>/", usr.ClientDetailView.as_view(), name="client_detail"),
    path("clients/<int:pk>/suspendre/", usr.ClientSuspendView.as_view(), name="client_suspend"),
    path("clients/<int:pk>/reactiver/", usr.ClientReactivateView.as_view(), name="client_reactivate"),
    path("clients/<int:pk>/supprimer/", usr.ClientDeleteView.as_view(), name="client_delete"),
    # Prestataires
    path("prestataires/", usr.ProviderListView.as_view(), name="providers"),
    path("prestataires/<int:pk>/", usr.ProviderDetailView.as_view(), name="provider_detail"),
    path("prestataires/<int:pk>/modifier/", usr.ProviderEditView.as_view(), name="provider_edit"),
    path("prestataires/<int:pk>/valider/", usr.ProviderApproveView.as_view(), name="provider_approve"),
    path("prestataires/<int:pk>/refuser/", usr.ProviderRejectView.as_view(), name="provider_reject"),
    path("prestataires/<int:pk>/suspendre/", usr.ProviderSuspendView.as_view(), name="provider_suspend"),
    path("prestataires/<int:pk>/reactiver/", usr.ProviderReactivateView.as_view(), name="provider_reactivate"),
    path("prestataires/<int:pk>/badge/", usr.ProviderVerifiedToggleView.as_view(), name="provider_verified"),
    path("prestataires/<int:pk>/mise-en-avant/", usr.ProviderFeaturedToggleView.as_view(), name="provider_featured"),
    path("prestataires/<int:pk>/metier/valider/", usr.CategoryChangeApproveView.as_view(), name="category_change_approve"),
    path("prestataires/<int:pk>/metier/refuser/", usr.CategoryChangeRejectView.as_view(), name="category_change_reject"),
    path("verifications/", usr.VerificationListView.as_view(), name="verifications"),
    path("verifications/<int:pk>/piece/<str:kind>/", usr.VerificationFileView.as_view(), name="verification_file"),
    path("verifications/<int:pk>/approuver/", usr.VerificationApproveView.as_view(), name="verification_approve"),
    path("verifications/<int:pk>/refuser/", usr.VerificationRejectView.as_view(), name="verification_reject"),
    # Catalogue
    path("categories/", cat.CategoryListView.as_view(), name="categories"),
    path("categories/nouvelle/", cat.CategoryFormView.as_view(), name="category_new"),
    path("categories/<int:pk>/modifier/", cat.CategoryFormView.as_view(), name="category_edit"),
    path("categories/<int:pk>/supprimer/", cat.CategoryDeleteView.as_view(), name="category_delete"),
    path("categories/<int:pk>/activer/", cat.CategoryToggleView.as_view(), name="category_toggle"),
    path("categories/<int:pk>/champs/", cat.CategoryFieldsView.as_view(), name="category_fields"),
    path("champs/nouveau/", cat.FieldFormView.as_view(), name="field_new"),
    path("champs/<int:pk>/modifier/", cat.FieldFormView.as_view(), name="field_edit"),
    path("champs/<int:pk>/supprimer/", cat.FieldDeleteView.as_view(), name="field_delete"),
    path("champs/<int:pk>/activer/", cat.FieldToggleView.as_view(), name="field_toggle"),
    path("sous-categories/nouvelle/", cat.SubcategoryFormView.as_view(), name="subcategory_new"),
    path("sous-categories/<int:pk>/modifier/", cat.SubcategoryFormView.as_view(), name="subcategory_edit"),
    path("sous-categories/<int:pk>/supprimer/", cat.SubcategoryDeleteView.as_view(), name="subcategory_delete"),
    path("sous-categories/<int:pk>/activer/", cat.SubcategoryToggleView.as_view(), name="subcategory_toggle"),
    path("villes/", cat.CityListView.as_view(), name="cities"),
    path("villes/nouvelle/", cat.CityFormView.as_view(), name="city_new"),
    path("villes/<int:pk>/modifier/", cat.CityFormView.as_view(), name="city_edit"),
    path("villes/<int:pk>/supprimer/", cat.CityDeleteView.as_view(), name="city_delete"),
    path("villes/<int:pk>/activer/", cat.CityToggleView.as_view(), name="city_toggle"),
    path("quartiers/nouveau/", cat.NeighborhoodFormView.as_view(), name="neighborhood_new"),
    path("quartiers/<int:pk>/modifier/", cat.NeighborhoodFormView.as_view(), name="neighborhood_edit"),
    path("quartiers/<int:pk>/supprimer/", cat.NeighborhoodDeleteView.as_view(), name="neighborhood_delete"),
    path("quartiers/<int:pk>/activer/", cat.NeighborhoodToggleView.as_view(), name="neighborhood_toggle"),
    # Demandes, avis, signalements
    path("demandes/", mod.RequestListView.as_view(), name="requests"),
    path("demandes/<int:pk>/", mod.RequestDetailView.as_view(), name="request_detail"),
    path("demandes/<int:pk>/annuler/", mod.RequestCancelView.as_view(), name="request_cancel"),
    path("demandes/<int:pk>/mediation/", mod.RequestMediateView.as_view(), name="request_mediate"),
    path("avis/", mod.ReviewListView.as_view(), name="reviews"),
    path("avis/<int:pk>/masquer/", mod.ReviewHideView.as_view(), name="review_hide"),
    path("avis/<int:pk>/retablir/", mod.ReviewRestoreView.as_view(), name="review_restore"),
    path("avis/<int:pk>/supprimer/", mod.ReviewDeleteView.as_view(), name="review_delete"),
    path("signalements/", mod.ReportListView.as_view(), name="reports"),
    path("signalements/<int:pk>/", mod.ReportDetailView.as_view(), name="report_detail"),
    path("signalements/<int:pk>/traiter/", mod.ReportTreatView.as_view(), name="report_treat"),
    # Contenu et communication
    path("contenu/", cnt.ContentView.as_view(), name="content"),
    path("contenu/bannieres/nouvelle/", cnt.BannerFormView.as_view(), name="banner_new"),
    path("contenu/bannieres/<int:pk>/modifier/", cnt.BannerFormView.as_view(), name="banner_edit"),
    path("contenu/bannieres/<int:pk>/supprimer/", cnt.BannerDeleteView.as_view(), name="banner_delete"),
    path("contenu/bannieres/<int:pk>/activer/", cnt.BannerToggleView.as_view(), name="banner_toggle"),
    path("contenu/pages/nouvelle/", cnt.PageFormView.as_view(), name="page_new"),
    path("contenu/pages/<int:pk>/modifier/", cnt.PageFormView.as_view(), name="page_edit"),
    path("contenu/pages/<int:pk>/supprimer/", cnt.PageDeleteView.as_view(), name="page_delete"),
    path("contenu/pages/<int:pk>/publier/", cnt.PageToggleView.as_view(), name="page_toggle"),
    path("contenu/faq/nouvelle/", cnt.FAQFormView.as_view(), name="faq_new"),
    path("contenu/faq/<int:pk>/modifier/", cnt.FAQFormView.as_view(), name="faq_edit"),
    path("contenu/faq/<int:pk>/supprimer/", cnt.FAQDeleteView.as_view(), name="faq_delete"),
    path("contenu/faq/<int:pk>/activer/", cnt.FAQToggleView.as_view(), name="faq_toggle"),
    path("contenu/mise-en-avant/<int:pk>/retirer/", cnt.UnfeatureView.as_view(), name="unfeature"),
    path("communication/", cnt.CommunicationView.as_view(), name="communication"),
    path("communication/notification/", cnt.TargetedNotificationView.as_view(), name="notification_send"),
    # Équipe, audit, paramètres
    path("equipe/", sys.TeamView.as_view(), name="team"),
    path("equipe/nouveau/", sys.TeamFormView.as_view(), name="team_new"),
    path("equipe/<int:pk>/", sys.TeamFormView.as_view(), name="team_edit"),
    path("equipe/<int:pk>/activer/", sys.TeamToggleView.as_view(), name="team_toggle"),
    path("audit/", sys.AuditView.as_view(), name="audit"),
    path("parametres/", sys.SettingsView.as_view(), name="settings"),
]
