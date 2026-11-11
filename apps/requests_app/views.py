from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.accounts.models import User
from apps.core import ratelimit
from apps.core.mixins import RoleRequiredMixin
from apps.providers.models import ProviderProfile

from . import services
from .forms import ServiceRequestForm
from .models import Quote, ServiceRequest

S = ServiceRequest.Status
DAILY_REQUEST_LIMIT = 10

FILTERS = {
    "toutes": None,
    "en-cours": services.OPEN_STATUSES,
    "terminees": (S.DONE,),
    "fermees": services.CLOSED_STATUSES,
}


class ClientOnly(RoleRequiredMixin):
    allowed_roles = (User.Role.CLIENT,)


class RequestCreateView(ClientOnly, FormView):
    template_name = "requests_app/create.html"
    form_class = ServiceRequestForm

    def dispatch(self, request, *args, **kwargs):
        self.provider = get_object_or_404(
            ProviderProfile.objects.public().select_related("city", "category"), slug=kwargs["slug"]
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        profile = getattr(self.request.user, "client_profile", None)
        initial = {"city": (profile.city if profile and profile.city_id else self.provider.city)}
        if profile and profile.address:
            initial["address"] = profile.address
        service = self.provider.services.filter(pk=self.request.GET.get("service") or 0, is_active=True).first()
        if service:
            initial["description"] = f"{service.title} : "
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["provider"] = self.provider
        return ctx

    def form_valid(self, form):
        user = self.request.user
        if ratelimit.is_limited("request_create", str(user.pk), DAILY_REQUEST_LIMIT):
            messages.error(self.request, _("Vous avez atteint la limite de demandes pour aujourd'hui. Réessayez demain."))
            return self.render_to_response(self.get_context_data(form=form), status=429)
        data = form.cleaned_data
        photos = data.pop("photos", [])
        req = services.create_request(client=user, provider=self.provider, photos=photos, **data)
        ratelimit.hit("request_create", str(user.pk), 24 * 3600)
        messages.success(self.request, _("Votre demande a été envoyée à %(name)s.") % {"name": self.provider.business_name})
        return redirect("requests_app:detail", pk=req.pk)


class MyRequestsView(ClientOnly, TemplateView):
    template_name = "requests_app/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        key = self.request.GET.get("statut", "toutes")
        key = key if key in FILTERS else "toutes"
        base = ServiceRequest.objects.filter(client=self.request.user)
        qs = base.select_related("provider", "provider__category", "provider__city").order_by("-updated_at")
        if FILTERS[key]:
            qs = qs.filter(status__in=FILTERS[key])
        page = Paginator(qs, 10).get_page(self.request.GET.get("page"))
        counts = {k: (base.filter(status__in=v).count() if v else base.count()) for k, v in FILTERS.items()}
        reviewed = set(
            self.request.user.reviews_written.filter(request__in=[r.pk for r in page.object_list]).values_list("request_id", flat=True)
        )
        ctx.update(
            page_obj=page, requests=page.object_list, current=key, counts=counts, reviewed_ids=reviewed,
            tabs=[("toutes", _("Toutes")), ("en-cours", _("En cours")), ("terminees", _("Terminées")), ("fermees", _("Annulées / refusées"))],
            nav_section="requests",
        )
        return ctx


STEPS = [S.SENT, S.VIEWED, S.QUOTED, S.ACCEPTED, S.IN_PROGRESS, S.DONE]


class RequestDetailView(ClientOnly, TemplateView):
    template_name = "requests_app/detail.html"

    def get_context_data(self, pk, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = get_object_or_404(
            ServiceRequest.objects.select_related("provider", "provider__city", "provider__category", "city"),
            pk=pk, client=self.request.user,
        )
        index = STEPS.index(req.status) if req.status in STEPS else -1
        labels = dict(S.choices)
        steps = [{"label": labels[s], "done": i <= index, "current": i == index} for i, s in enumerate(STEPS)]
        review = getattr(req, "review", None) if hasattr(req, "review") else None
        ctx.update(
            req=req, steps=steps, quotes=req.quotes.all(), photos=req.photos.all(), review=review,
            can_cancel=req.status in services.CLIENT_CANCELLABLE,
            can_review=req.status == S.DONE and review is None,
            nav_section="requests",
        )
        return ctx


class _ActionView(ClientOnly, View):
    http_method_names = ["post"]
    success_message = ""
    error_message = _("Cette action n'est plus possible pour cette demande.")

    def act(self, request, pk):  # pragma: no cover
        raise NotImplementedError

    def post(self, request, pk):
        try:
            self.act(request, pk)
        except services.InvalidTransition:
            messages.error(request, self.error_message)
        else:
            messages.success(request, self.success_message)
        return redirect("requests_app:detail", pk=self.request_pk(pk))

    def request_pk(self, pk):
        return pk


class CancelRequestView(_ActionView):
    success_message = _("Votre demande a été annulée.")

    def act(self, request, pk):
        req = get_object_or_404(ServiceRequest, pk=pk, client=request.user)
        services.cancel_by_client(req, request.user)


class _QuoteAction(_ActionView):
    def quote(self, request, pk):
        return get_object_or_404(Quote.objects.select_related("request"), pk=pk, request__client=request.user)

    def request_pk(self, pk):
        return Quote.objects.values_list("request_id", flat=True).get(pk=pk)


class AcceptQuoteView(_QuoteAction):
    success_message = _("Devis accepté. Le prestataire est prévenu.")
    error_message = _("Ce devis ne peut plus être accepté (il a peut-être expiré).")

    def act(self, request, pk):
        services.accept_quote(self.quote(request, pk), request.user)


class DeclineQuoteView(_QuoteAction):
    success_message = _("Devis refusé. Le prestataire peut vous en proposer un autre.")

    def act(self, request, pk):
        services.decline_quote(self.quote(request, pk), request.user)
