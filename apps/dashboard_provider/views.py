from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.accounts.models import User
from apps.core.images import compress_image
from apps.core.mixins import RoleRequiredMixin
from apps.core.site_settings import portfolio_limit
from apps.providers.models import PortfolioMedia, ProviderProfile, Service, Verification
from apps.requests_app import services as request_services
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Review

from . import stats
from .forms import (
    AvailabilityForm, CaptionForm, PortfolioUploadForm, ProfileForm, ProviderAccountForm, QuoteForm, RefuseForm,
    ReplyForm, ServiceForm, VerificationForm,
)

S = ServiceRequest.Status


class ProviderOnly(RoleRequiredMixin):
    allowed_roles = (User.Role.PROVIDER,)

    @property
    def profile(self):
        return self.request.user.provider_profile

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profile"] = self.profile
        return ctx


def completeness(profile):
    """Éléments à compléter pour un profil attractif : (libellé, fait, lien)."""
    checks = [
        (_("Photo ou logo"), bool(profile.logo), "dashboard_provider:profile"),
        (_("Description de votre activité"), len(profile.description.strip()) >= 30, "dashboard_provider:profile"),
        (_("Au moins un service avec tarif"), profile.services.filter(is_active=True).exists(), "dashboard_provider:services"),
        (_("Au moins 3 photos de réalisations"), profile.portfolio.count() >= 3, "dashboard_provider:portfolio"),
        (_("Horaires renseignés"), profile.availabilities.exists(), "dashboard_provider:availability"),
        (_("Compte vérifié"), profile.is_verified, "dashboard_provider:verification"),
    ]
    items = [{"label": label, "done": done, "url": reverse(url)} for label, done, url in checks]
    return items, round(100 * sum(i["done"] for i in items) / len(items))


# --- Tableau de bord ---------------------------------------------------------
class HomeView(ProviderOnly, TemplateView):
    template_name = "dashboard_provider/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.profile
        rows = stats.daily_series(profile, 30)
        items, percent = completeness(profile)
        ctx.update(
            kpi=stats.request_kpis(profile), chart_rows=[
                {"date": r["date"].strftime("%d/%m"), "views": r["views"], "clicks": r["clicks"], "requests": r["requests"]} for r in rows
            ],
            totals30=stats.totals(rows), checklist=items, completeness=percent,
            latest=list(profile.service_requests.select_related("client", "city")[:5]),
        )
        return ctx


# --- Profil ------------------------------------------------------------------
class ProfileView(ProviderOnly, FormView):
    template_name = "dashboard_provider/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("dashboard_provider:profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.profile
        return kwargs

    def form_valid(self, form):
        had_pending = bool(self.profile.pending_category_id)
        form.save()
        if form.cleaned_data.get("new_category") and not had_pending:
            messages.info(self.request, _("Votre demande de changement de métier a été transmise à l'équipe Kora."))
        messages.success(self.request, _("Votre profil a été enregistré."))
        return super().form_valid(form)


# --- Portfolio ---------------------------------------------------------------
class PortfolioView(ProviderOnly, FormView):
    template_name = "dashboard_provider/portfolio.html"
    form_class = PortfolioUploadForm
    success_url = reverse_lazy("dashboard_provider:portfolio")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["remaining"] = max(0, portfolio_limit() - self.profile.portfolio.count())
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(items=self.profile.portfolio.all(), limit=portfolio_limit())
        return ctx

    def form_valid(self, form):
        last = self.profile.portfolio.order_by("-order").values_list("order", flat=True).first() or 0
        for i, image in enumerate(form.cleaned_data["images"], start=1):
            PortfolioMedia.objects.create(provider=self.profile, image=compress_image(image), order=last + i)
        messages.success(self.request, _("Photos ajoutées à votre portfolio."))
        return super().form_valid(form)


class _PortfolioAction(ProviderOnly, View):
    http_method_names = ["post"]

    def item(self, pk):
        return get_object_or_404(PortfolioMedia, pk=pk, provider=self.profile)


class PortfolioCaptionView(_PortfolioAction):
    def post(self, request, pk):
        item = self.item(pk)
        form = CaptionForm(request.POST)
        if form.is_valid():
            item.caption = form.cleaned_data["caption"]
            item.save(update_fields=["caption"])
            messages.success(request, _("Légende enregistrée."))
        else:
            messages.error(request, _("Légende trop longue (160 caractères maximum)."))
        return redirect("dashboard_provider:portfolio")


class PortfolioMoveView(_PortfolioAction):
    def post(self, request, pk, direction):
        item = self.item(pk)
        items = list(self.profile.portfolio.all())
        i = items.index(item)
        j = i - 1 if direction == "haut" else i + 1
        if 0 <= j < len(items):
            items[i], items[j] = items[j], items[i]
            for order, it in enumerate(items):
                if it.order != order:
                    PortfolioMedia.objects.filter(pk=it.pk).update(order=order)
        return redirect("dashboard_provider:portfolio")


class PortfolioDeleteView(_PortfolioAction):
    def post(self, request, pk):
        item = self.item(pk)
        item.image.delete(save=False)
        item.delete()
        messages.success(request, _("Photo supprimée."))
        return redirect("dashboard_provider:portfolio")


# --- Services ----------------------------------------------------------------
class ServiceListView(ProviderOnly, TemplateView):
    template_name = "dashboard_provider/services.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["services"] = self.profile.services.all()
        return ctx


class ServiceFormView(ProviderOnly, FormView):
    template_name = "dashboard_provider/service_form.html"
    form_class = ServiceForm
    success_url = reverse_lazy("dashboard_provider:services")

    def dispatch(self, request, *args, **kwargs):
        self.service = None
        return super().dispatch(request, *args, **kwargs)

    def get_service(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(Service, pk=pk, provider=self.profile) if pk else None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.service = self.get_service()
        kwargs["instance"] = self.service
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["service"] = self.service
        return ctx

    def form_valid(self, form):
        service = form.save(commit=False)
        service.provider = self.profile
        service.save()
        messages.success(self.request, _("Service enregistré."))
        return super().form_valid(form)


class ServiceDeleteView(ProviderOnly, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        get_object_or_404(Service, pk=pk, provider=self.profile).delete()
        messages.success(request, _("Service supprimé."))
        return redirect("dashboard_provider:services")


class ServiceToggleView(ProviderOnly, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        service = get_object_or_404(Service, pk=pk, provider=self.profile)
        service.is_active = not service.is_active
        service.save(update_fields=["is_active"])
        messages.success(request, _("Service affiché sur votre fiche.") if service.is_active else _("Service masqué de votre fiche."))
        return redirect("dashboard_provider:services")


# --- Disponibilités ----------------------------------------------------------
class AvailabilityView(ProviderOnly, FormView):
    template_name = "dashboard_provider/availability.html"
    form_class = AvailabilityForm
    success_url = reverse_lazy("dashboard_provider:availability")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["profile"] = self.profile
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("Disponibilités enregistrées."))
        return super().form_valid(form)


# --- Demandes ----------------------------------------------------------------
REQUEST_FILTERS = {
    "toutes": None,
    "nouvelles": (S.SENT, S.VIEWED),
    "devis": (S.QUOTED,),
    "en-cours": (S.ACCEPTED, S.IN_PROGRESS),
    "terminees": (S.DONE,),
    "fermees": (S.CANCELLED, S.REFUSED),
}


class RequestListView(ProviderOnly, TemplateView):
    template_name = "dashboard_provider/requests.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = ServiceRequest.objects.filter(provider=self.profile)
        key = self.request.GET.get("statut", "toutes")
        key = key if key in REQUEST_FILTERS else "toutes"
        q = self.request.GET.get("q", "").strip()[:100]
        qs = base.select_related("client", "city")
        if REQUEST_FILTERS[key]:
            qs = qs.filter(status__in=REQUEST_FILTERS[key])
        if q:
            qs = qs.filter(Q(description__icontains=q) | Q(client__first_name__icontains=q) | Q(client__last_name__icontains=q))
        labels = {"toutes": _("Toutes"), "nouvelles": _("Nouvelles"), "devis": _("Devis envoyés"), "en-cours": _("En cours"), "terminees": _("Terminées"), "fermees": _("Fermées")}
        ctx.update(
            page_obj=Paginator(qs, 15).get_page(self.request.GET.get("page")), current=key, q=q,
            tabs=[(k, labels[k], base.filter(status__in=v).count() if v else base.count()) for k, v in REQUEST_FILTERS.items()],
        )
        return ctx


class RequestDetailView(ProviderOnly, TemplateView):
    template_name = "dashboard_provider/request_detail.html"

    def get_request(self):
        return get_object_or_404(
            ServiceRequest.objects.select_related("client", "city"), pk=self.kwargs["pk"], provider=self.profile
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = self.get_request()
        if req.status == S.SENT and self.profile.status == ProviderProfile.Status.ACTIVE:
            req = request_services.change_status(req, S.VIEWED, self.request.user)  # le client est prévenu
        ctx.update(
            req=req, photos=req.photos.all(), quotes=req.quotes.all(), quote_form=kwargs.get("quote_form") or QuoteForm(),
            refuse_form=RefuseForm(), review=getattr(req, "review", None),
            can_quote=req.status in request_services.QUOTABLE, can_accept=req.status in (S.SENT, S.VIEWED, S.QUOTED),
            can_refuse=req.status in (S.SENT, S.VIEWED, S.QUOTED), can_start=req.status == S.ACCEPTED, can_finish=req.status == S.IN_PROGRESS,
            active=self.profile.status == ProviderProfile.Status.ACTIVE,
        )
        return ctx


class _RequestAction(ProviderOnly, View):
    http_method_names = ["post"]
    success_message = ""

    def get_request(self, pk):
        return get_object_or_404(ServiceRequest, pk=pk, provider=self.profile)

    def post(self, request, pk):
        req = self.get_request(pk)
        if self.profile.status != ProviderProfile.Status.ACTIVE:
            messages.error(request, _("Votre compte n'est pas actif : vous ne pouvez pas traiter de demandes."))
            return redirect("dashboard_provider:request_detail", pk=pk)
        try:
            response = self.act(request, req)
        except request_services.InvalidTransition:
            messages.error(request, _("Cette action n'est plus possible pour cette demande."))
        else:
            if response is not None:
                return response
            messages.success(request, self.success_message)
        return redirect("dashboard_provider:request_detail", pk=pk)

    def act(self, request, req):  # pragma: no cover
        raise NotImplementedError


class RequestAcceptView(_RequestAction):
    success_message = _("Demande acceptée. Le client est prévenu.")

    def act(self, request, req):
        request_services.change_status(req, S.ACCEPTED, request.user)


class RequestRefuseView(_RequestAction):
    success_message = _("Demande refusée. Le client est prévenu.")

    def act(self, request, req):
        form = RefuseForm(request.POST)
        form.is_valid()
        request_services.change_status(req, S.REFUSED, request.user, reason=form.cleaned_data.get("reason", ""))


class RequestStartView(_RequestAction):
    success_message = _("Prestation marquée « en cours ».")

    def act(self, request, req):
        request_services.change_status(req, S.IN_PROGRESS, request.user)


class RequestFinishView(_RequestAction):
    success_message = _("Prestation terminée. Le client pourra maintenant donner son avis.")

    def act(self, request, req):
        request_services.change_status(req, S.DONE, request.user)


class RequestQuoteView(_RequestAction):
    success_message = _("Devis envoyé au client.")

    def act(self, request, req):
        form = QuoteForm(request.POST)
        if not form.is_valid():
            view = RequestDetailView()
            view.setup(request, pk=req.pk)
            ctx = view.get_context_data(quote_form=form)
            from django.shortcuts import render

            messages.error(request, _("Le devis n'a pas été envoyé : vérifiez les champs."))
            return render(request, view.template_name, {**ctx, "request": request, "view": view})
        request_services.send_quote(req, request.user, **form.cleaned_data)


# --- Avis --------------------------------------------------------------------
class ReviewListView(ProviderOnly, TemplateView):
    template_name = "dashboard_provider/reviews.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.profile.reviews.exclude(status=Review.Status.HIDDEN).select_related("client", "request")
        ctx.update(page_obj=Paginator(qs, 10).get_page(self.request.GET.get("page")), reply_form=ReplyForm())
        return ctx


class ReviewReplyView(ProviderOnly, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk, provider=self.profile, status=Review.Status.VISIBLE)
        form = ReplyForm(request.POST)
        if form.is_valid():
            review.provider_reply, review.replied_at = form.cleaned_data["reply"], timezone.now()
            review.save(update_fields=["provider_reply", "replied_at", "updated_at"])
            messages.success(request, _("Votre réponse est publiée."))
        else:
            messages.error(request, _("Écrivez votre réponse (1000 caractères maximum)."))
        return redirect("dashboard_provider:reviews")


# --- Statistiques ------------------------------------------------------------
class StatsView(ProviderOnly, TemplateView):
    template_name = "dashboard_provider/stats.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            days = int(self.request.GET.get("periode", 30))
        except ValueError:
            days = 30
        days = days if days in stats.PERIODS else 30
        rows = stats.daily_series(self.profile, days)
        ctx.update(
            days=days, periods=stats.PERIODS, totals=stats.totals(rows), kpi=stats.request_kpis(self.profile),
            rows=[r for r in reversed(rows) if r["views"] or r["clicks"] or r["requests"]],
            chart_rows=[{"date": r["date"].strftime("%d/%m"), "views": r["views"], "clicks": r["clicks"], "requests": r["requests"]} for r in rows],
        )
        return ctx


# --- Vérification ------------------------------------------------------------
class VerificationView(ProviderOnly, FormView):
    template_name = "dashboard_provider/verification.html"
    form_class = VerificationForm
    success_url = reverse_lazy("dashboard_provider:verification")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        history = list(self.profile.verifications.all())
        ctx.update(history=history, pending=any(v.status == Verification.Status.PENDING for v in history))
        return ctx

    def post(self, request, *args, **kwargs):
        if self.profile.verifications.filter(status=Verification.Status.PENDING).exists():
            messages.error(request, _("Un dossier est déjà en cours d'examen."))
            return redirect(self.success_url)
        if self.profile.is_verified:
            messages.info(request, _("Votre compte est déjà vérifié."))
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        verification = form.save(commit=False)
        verification.provider = self.profile
        verification.save()
        messages.success(self.request, _("Dossier envoyé. Vous serez notifié dès qu'il aura été examiné."))
        return super().form_valid(form)


# --- Paramètres --------------------------------------------------------------
class SettingsView(ProviderOnly, FormView):
    template_name = "dashboard_provider/settings.html"
    form_class = ProviderAccountForm
    success_url = reverse_lazy("dashboard_provider:settings")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, _("Vos paramètres ont été enregistrés."))
        response = redirect(self.get_success_url())
        from django.conf import settings

        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user.language, max_age=365 * 24 * 3600, samesite="Lax")
        return response
