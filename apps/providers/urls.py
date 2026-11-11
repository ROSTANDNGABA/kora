from django.urls import path

from . import views

app_name = "providers"

urlpatterns = [
    path("<slug:slug>/", views.ProviderDetailView.as_view(), name="detail"),
    path("<slug:slug>/avis/", views.ReviewsFragmentView.as_view(), name="reviews"),
    path("<slug:slug>/whatsapp/", views.WhatsAppRedirectView.as_view(), name="whatsapp"),
]
