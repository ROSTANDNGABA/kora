from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from .models import FAQ, StaticPage


class StaticPageView(DetailView):
    """Pages éditées par l'admin : À propos, CGU, confidentialité."""

    template_name = "cms/page.html"
    context_object_name = "page"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return StaticPage.objects.filter(is_published=True)


class FAQView(TemplateView):
    template_name = "cms/faq.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["faqs"] = FAQ.objects.filter(is_active=True)
        return ctx
