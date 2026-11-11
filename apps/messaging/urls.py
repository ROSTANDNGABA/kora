from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("messages/", views.InboxView.as_view(), name="inbox"),
    path("messages/<int:pk>/", views.ThreadView.as_view(), name="thread"),
    path("messages/<int:pk>/fil/", views.ThreadFragmentView.as_view(), name="thread_fragment"),
    path("messages/nouveau/<slug:slug>/", views.StartFromProviderView.as_view(), name="start"),
    path("messages/demande/<int:pk>/", views.StartFromRequestView.as_view(), name="start_from_request"),
]
