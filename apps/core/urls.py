from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("mon-espace/", views.ClientHomeView.as_view(), name="client_home"),
    path("design-system/", views.DesignSystemView.as_view(), name="design_system"),
]
