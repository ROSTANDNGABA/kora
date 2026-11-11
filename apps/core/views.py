from types import SimpleNamespace

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import TemplateView

from apps.accounts.models import User

from .landing import landing_context
from .mixins import RoleRequiredMixin


class HomeView(TemplateView):
    """Page d'accueil publique, commune à tous les rôles."""

    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(landing_context())
        from apps.cms.models import Banner

        ctx["banners"] = list(Banner.objects.filter(is_active=True)[:3])
        return ctx


class ClientHomeView(RoleRequiredMixin, TemplateView):
    """Accueil du client connecté : demandes en cours, avis à donner, favoris et suggestions."""

    allowed_roles = (User.Role.CLIENT,)
    template_name = "client/home.html"

    def get_context_data(self, **kwargs):
        from apps.favorites.models import Favorite
        from apps.providers.selectors import public_cards
        from apps.requests_app.models import ServiceRequest
        from apps.requests_app.services import OPEN_STATUSES

        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        requests = ServiceRequest.objects.filter(client=user)
        to_review = list(
            requests.filter(status=ServiceRequest.Status.DONE, review__isnull=True)
            .select_related("provider").order_by("-completed_at")[:3]
        )
        profile = getattr(user, "client_profile", None)
        suggestions = public_cards()
        if profile and profile.city_id:
            suggestions = suggestions.filter(city_id=profile.city_id)
        favorite_ids = list(Favorite.objects.filter(user=user).values_list("provider_id", flat=True))
        ctx.update(
            open_requests=list(requests.filter(status__in=OPEN_STATUSES).select_related("provider").order_by("-updated_at")[:4]),
            open_count=requests.filter(status__in=OPEN_STATUSES).count(),
            to_review=to_review,
            favorites_count=len(favorite_ids),
            searches=list(user.saved_searches.all()[:3]),
            suggestions=list(suggestions.exclude(pk__in=favorite_ids).order_by("-is_verified", "-rating_avg")[:3]),
            city=profile.city if profile else None,
            search_page_url=reverse("catalog:search"),
        )
        return ctx


class DesignSystemView(TemplateView):
    """Catalogue des composants. Visible seulement en mode DEBUG."""

    template_name = "core/design_system.html"

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        def fake(name, trade, city, rating, reviews, verified, color):
            return SimpleNamespace(
                business_name=name, main_trade=trade, city=SimpleNamespace(name=city), rating_avg=rating,
                reviews_count=reviews, is_verified=verified, logo="", category=SimpleNamespace(color=color),
            )

        ctx["providers"] = [
            fake("Atelier Mballa", "Couturier", "Yaoundé", 4.8, 124, True, "#F36F21"),
            fake("Chantal Nguemo", "Pâtissière", "Douala", 4.5, 58, False, "#5B9E2D"),
            fake("Paul Tchoumi", "Plombier", "Bafoussam", 0, 0, True, "#1D9BF0"),
        ]
        ctx["categories"] = [
            {"name": "Couture & Stylisme", "icon": "scissors", "color": "#F36F21"},
            {"name": "Cuisine & Pâtisserie", "icon": "chef-hat", "color": "#F5B800"},
            {"name": "Plomberie", "icon": "droplets", "color": "#2F80ED"},
            {"name": "Menuiserie & Bricolage", "icon": "hammer", "color": "#8B5A2B"},
            {"name": "Services Numériques", "icon": "monitor-smartphone", "color": "#7C4DFF"},
            {"name": "Mécanique & Électricité", "icon": "wrench", "color": "#5B9E2D"},
        ]
        return ctx


def permission_denied(request, exception=None):
    return render(request, "errors/403.html", status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)
