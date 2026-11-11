from urllib.parse import parse_qsl, urlencode

from django.contrib import messages
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.models import User
from apps.catalog.filters import FILTER_KEYS
from apps.core.mixins import RoleRequiredMixin
from apps.providers.models import ProviderProfile
from apps.providers.selectors import public_cards

from .models import Favorite, SavedSearch

MAX_SAVED_SEARCHES = 30


class ClientOnly(RoleRequiredMixin):
    allowed_roles = (User.Role.CLIENT,)


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _safe_next(request, default):
    target = request.POST.get("next", "")
    ok = url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    return target if ok and target else default


class FavoriteListView(ClientOnly, TemplateView):
    template_name = "favorites/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tab = "recherches" if self.request.GET.get("onglet") == "recherches" else "artisans"
        favorites = Favorite.objects.filter(user=self.request.user).values_list("provider_id", flat=True)
        # Les favoris dont le prestataire n'est plus public (suspendu...) ne sont pas affichés.
        providers = public_cards().filter(pk__in=favorites)
        order = {pk: i for i, pk in enumerate(favorites)}
        providers = sorted(providers, key=lambda p: order[p.pk])
        ctx.update(
            tab=tab, providers=providers, favorites_list=True,
            searches=self.request.user.saved_searches.all(),
            nav_section="favorites",
        )
        return ctx


class FavoriteToggleView(ClientOnly, View):
    http_method_names = ["post"]

    def post(self, request, provider_id):
        provider = get_object_or_404(ProviderProfile.objects.public(), pk=provider_id)
        fav, created = Favorite.objects.get_or_create(user=request.user, provider=provider)
        if not created:
            fav.delete()
        in_list = request.POST.get("from") == "list"
        if _is_htmx(request):
            if in_list and not created:
                return HttpResponse("")  # la carte disparaît de la liste
            html = render_to_string(
                "favorites/partials/heart.html",
                {
                    "show": True, "provider": provider, "anonymous": False, "is_favorite": created, "in_list": in_list,
                    "csrf_token": get_token(request), "next": _safe_next(request, ""),
                },
                request=request,
            )
            return HttpResponse(html)
        messages.success(request, _("Ajouté à vos favoris.") if created else _("Retiré de vos favoris."))
        return redirect(_safe_next(request, provider.get_absolute_url()))


class SaveSearchView(ClientOnly, View):
    http_method_names = ["post"]

    def post(self, request):
        # On ne garde que les critères connus : un client ne peut pas enregistrer de paramètres arbitraires.
        pairs = [(k, v) for k, v in parse_qsl(request.POST.get("query_string", ""), keep_blank_values=False) if k in FILTER_KEYS]
        query_string = urlencode(pairs)[:500]
        if not query_string:
            messages.error(request, _("Aucun critère à enregistrer."))
            return redirect("catalog:search")
        label = (request.POST.get("label") or _("Recherche"))[:120]
        searches = request.user.saved_searches
        if not searches.filter(query_string=query_string).exists() and searches.count() >= MAX_SAVED_SEARCHES:
            messages.error(request, _("Vous avez atteint la limite de %(n)d recherches enregistrées.") % {"n": MAX_SAVED_SEARCHES})
        else:
            searches.get_or_create(query_string=query_string, defaults={"label": label})
            if _is_htmx(request):
                return HttpResponse(
                    '<span class="badge-green" role="status">' + str(_("Recherche enregistrée")) + "</span>"
                )
            messages.success(request, _("Recherche enregistrée. Retrouvez-la dans vos favoris."))
        return redirect(f"{reverse('catalog:search')}?{query_string}")


class DeleteSearchView(ClientOnly, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
        search.delete()
        if _is_htmx(request):
            return HttpResponse("")
        messages.success(request, _("Recherche supprimée."))
        return redirect(f"{reverse('favorites:list')}?onglet=recherches")
