"""Sitemap et robots.txt."""
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse

from apps.catalog.models import Category
from apps.cms.models import StaticPage
from apps.providers.models import ProviderProfile


class HomeSitemap(Sitemap):
    changefreq, priority = "daily", 1.0

    def items(self):
        return ["core:home", "cms:faq", "catalog:search"]

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    changefreq, priority = "weekly", 0.8

    def items(self):
        return Category.objects.filter(is_active=True)


class StaticPageSitemap(Sitemap):
    changefreq, priority = "monthly", 0.3

    def items(self):
        return StaticPage.objects.filter(is_published=True)

    def location(self, obj):
        return reverse("cms:page", args=[obj.slug])

    def lastmod(self, obj):
        return obj.updated_at


class ProviderSitemap(Sitemap):
    changefreq, priority = "weekly", 0.6

    def items(self):
        return ProviderProfile.objects.public().order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {"providers": ProviderSitemap, "home": HomeSitemap, "categories": CategorySitemap, "pages": StaticPageSitemap}


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /compte/",
        "Disallow: /prestataire/",
        "Disallow: /back-office/",
        "Disallow: /django-admin/",
        "Disallow: /mes-demandes/",
        "Disallow: /mon-espace/",
        "Disallow: /messages/",
        "Disallow: /notifications/",
        "Disallow: /favoris/",
        "Disallow: /artisans/*/whatsapp/",
        "Disallow: /signaler/",
        "Disallow: /design-system/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
