from django.urls import path

from . import views

app_name = "cms"

urlpatterns = [
    path("faq/", views.FAQView.as_view(), name="faq"),
    path("page/<slug:slug>/", views.StaticPageView.as_view(), name="page"),
]
