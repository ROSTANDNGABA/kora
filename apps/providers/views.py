import json
from datetime import date

from django.db.models import Count
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.reviews.models import Review

from .models import Availability, ProviderProfile
from .selectors import public_cards
from .stats import record_event

REVIEWS_PAGE_SIZE = 6
SIMILAR_COUNT = 3


def get_visible_provider(request, slug):
    """Prestataire public ; son propriétaire et les administrateurs peuvent aussi prévisualiser une fiche non publique."""
    provider = get_object_or_404(
        ProviderProfile.objects.select_related("category", "city", "user"), slug=slug,
    )
    if provider.is_public:
        return provider
    user = request.user
    if user.is_authenticated and (provider.user_id == user.pk or user.is_admin_role):
        return provider
    raise Http404


def _format_field_value(field, raw):
    if field.field_type == "BOOLEAN":
        return _("Oui") if str(raw).lower() in ("1", "true", "oui", "on") else None
    return raw.strip() or None


def _hours(provider):
    by_day = {a.weekday: a for a in provider.availabilities.all()}
    today = date.today().weekday()
    rows = []
    for number, label in Availability.Weekday.choices:
        a = by_day.get(number)
        if a is None:
            text = None
        elif a.is_closed or not (a.opens_at and a.closes_at):
            text = _("Fermé")
        else:
            text = f"{a.opens_at:%H:%M} – {a.closes_at:%H:%M}"
        rows.append({"label": label, "text": text, "today": number == today, "closed": text == _("Fermé")})
    return rows


def _reviews_page(provider, page):
    qs = provider.reviews.filter(status=Review.Status.VISIBLE).select_related("client").order_by("-created_at")
    start = (page - 1) * REVIEWS_PAGE_SIZE
    chunk = list(qs[start:start + REVIEWS_PAGE_SIZE + 1])
    return chunk[:REVIEWS_PAGE_SIZE], (page + 1 if len(chunk) > REVIEWS_PAGE_SIZE else None)


class ProviderDetailView(TemplateView):
    template_name = "providers/detail.html"

    def get_context_data(self, slug, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        provider = get_visible_provider(request, slug)
        self._count_view(provider)

        distribution = dict(
            provider.reviews.filter(status=Review.Status.VISIBLE).values_list("rating").annotate(n=Count("id")).order_by()
        )
        total = sum(distribution.values())
        bars = [
            {"stars": n, "count": distribution.get(n, 0), "pct": round(100 * distribution.get(n, 0) / total) if total else 0}
            for n in (5, 4, 3, 2, 1)
        ]
        reviews, next_page = _reviews_page(provider, 1)
        fields = []
        for fv in provider.field_values.select_related("field").order_by("field__order", "field_id"):
            value = _format_field_value(fv.field, fv.value)
            if value:
                fields.append({"label": fv.field.label, "value": value})
        similar = list(
            public_cards().filter(category=provider.category, city=provider.city).exclude(pk=provider.pk)
            .order_by("-is_verified", "-rating_avg")[:SIMILAR_COUNT]
        )
        user = request.user
        message = _("Bonjour, j'ai trouvé votre profil sur Kora et j'aimerais avoir des renseignements sur vos services.")
        ctx["json_ld"] = self._json_ld(provider)
        ctx.update(
            provider=provider, is_preview=not provider.is_public,
            services=provider.services.filter(is_active=True),
            portfolio=list(provider.portfolio.all()),
            subcategories=list(provider.subcategories.all()),
            hours=_hours(provider), fields=fields,
            review_items=reviews, next_reviews_page=next_page, rating_bars=bars, reviews_total=total,
            similar=similar, whatsapp_message=message,
            can_request=(not user.is_authenticated) or user.is_client,
            is_owner=user.is_authenticated and provider.user_id == user.pk,
        )
        return ctx

    def _json_ld(self, provider):
        data = {
            "@context": "https://schema.org", "@type": "LocalBusiness", "name": provider.business_name,
            "description": provider.description[:300] or provider.main_trade,
            "url": self.request.build_absolute_uri(provider.get_absolute_url()),
            "address": {"@type": "PostalAddress", "addressLocality": provider.city.name, "addressCountry": "CM"},
        }
        if provider.logo:
            data["image"] = self.request.build_absolute_uri(provider.logo.url)
        if provider.reviews_count:
            data["aggregateRating"] = {
                "@type": "AggregateRating", "ratingValue": str(provider.rating_avg),
                "reviewCount": provider.reviews_count, "bestRating": "5",
            }
        # « < » est échappé pour qu'une description ne puisse pas fermer la balise <script>.
        return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")

    def _count_view(self, provider):
        """Une vue par visiteur et par prestataire et par session ; le propriétaire ne gonfle pas ses propres chiffres."""
        request = self.request
        if request.user.is_authenticated and request.user.pk == provider.user_id:
            return
        if not provider.is_public:
            return
        seen = request.session.get("viewed_providers", [])
        if provider.pk in seen:
            return
        record_event(provider.pk, "views")
        request.session["viewed_providers"] = (seen + [provider.pk])[-200:]


class ReviewsFragmentView(TemplateView):
    """« Voir plus d'avis » (HTMX)."""

    template_name = "providers/partials/reviews_list.html"

    def get_context_data(self, slug, **kwargs):
        ctx = super().get_context_data(**kwargs)
        provider = get_visible_provider(self.request, slug)
        try:
            page = max(1, int(self.request.GET.get("page", 2)))
        except ValueError:
            page = 2
        reviews, next_page = _reviews_page(provider, page)
        ctx.update(provider=provider, review_items=reviews, next_reviews_page=next_page)
        return ctx


class WhatsAppRedirectView(View):
    """Compte le clic puis redirige vers WhatsApp (lien wa.me avec message pré-rempli)."""

    def get(self, request, slug):
        from apps.core.templatetags.kora_ui import whatsapp_url

        provider = get_object_or_404(ProviderProfile.objects.public(), slug=slug)
        key = f"wa_{provider.pk}"
        if not request.session.get(key):  # un seul clic compté par session et par prestataire
            record_event(provider.pk, "whatsapp_clicks")
            request.session[key] = True
        message = _("Bonjour %(name)s, j'ai trouvé votre profil sur Kora. J'aimerais avoir des renseignements sur vos services.") % {
            "name": provider.business_name
        }
        url = whatsapp_url(provider.whatsapp, message)
        if not url:
            raise Http404
        response = HttpResponseRedirect(url)
        response["X-Robots-Tag"] = "noindex"
        return response
