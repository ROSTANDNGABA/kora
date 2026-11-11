"""Routes racine. Chaque app expose son propre urls.py."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.seo import SITEMAPS, robots_txt

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("compte/", include("apps.accounts.urls")),
    path("prestataire/", include("apps.dashboard_provider.urls")),
    path("back-office/", include("apps.dashboard_admin.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path("artisans/", include("apps.providers.urls")),
    path("", include("apps.messaging.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.requests_app.urls")),
    path("", include("apps.reviews.urls")),
    path("", include("apps.favorites.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.cms.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    from django.urls import re_path
    from django.views.static import serve
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]

handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
