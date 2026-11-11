from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view(), name="list"),
    path("notifications/<int:pk>/ouvrir/", views.NotificationOpenView.as_view(), name="open"),
    path("notifications/tout-lire/", views.MarkAllReadView.as_view(), name="read_all"),
]
