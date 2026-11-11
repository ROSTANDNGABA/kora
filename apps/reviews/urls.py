from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("mes-demandes/<int:pk>/avis/", views.ReviewCreateView.as_view(), name="create"),
    path("avis/<int:pk>/modifier/", views.ReviewEditView.as_view(), name="edit"),
    path("signaler/<str:target>/<int:pk>/", views.ReportView.as_view(), name="report"),
]
