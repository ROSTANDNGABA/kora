from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import FormView

from apps.accounts.models import User
from apps.core.mixins import RoleRequiredMixin
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.providers.models import ProviderProfile
from apps.requests_app.models import ServiceRequest

from .forms import ReportForm, ReviewForm
from .models import Report, Review


class ReviewCreateView(RoleRequiredMixin, FormView):
    """Un seul avis par prestation, uniquement sur une demande terminée (RG-03)."""

    allowed_roles = (User.Role.CLIENT,)
    template_name = "reviews/form.html"
    form_class = ReviewForm

    def _load(self):
        self.service_request = get_object_or_404(
            ServiceRequest.objects.select_related("provider"), pk=self.kwargs["pk"], client=self.request.user
        )

    def get(self, request, *args, **kwargs):
        self._load()
        return self._guard() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._load()
        return self._guard() or super().post(request, *args, **kwargs)

    def _guard(self):
        req = self.service_request
        if req.status != ServiceRequest.Status.DONE:
            messages.error(self.request, _("Vous pourrez donner votre avis une fois la prestation terminée."))
            return redirect("requests_app:detail", pk=req.pk)
        if Review.objects.filter(request=req).exists():
            messages.info(self.request, _("Vous avez déjà donné votre avis sur cette prestation."))
            return redirect("requests_app:detail", pk=req.pk)
        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(req=self.service_request, provider=self.service_request.provider, editing=False)
        return ctx

    def form_valid(self, form):
        req = self.service_request
        review = form.save(commit=False)
        review.request, review.client, review.provider = req, self.request.user, req.provider
        review.save()  # la note moyenne du prestataire est recalculée par signal
        notify(
            req.provider.user, _("Nouvel avis : %(n)d/5") % {"n": review.rating},
            body=review.comment[:140], url=req.provider.get_absolute_url() + "#avis", type=Notification.Type.REVIEW,
        )
        messages.success(self.request, _("Merci ! Votre avis est publié."))
        return redirect("requests_app:detail", pk=req.pk)


class ReviewEditView(RoleRequiredMixin, FormView):
    allowed_roles = (User.Role.CLIENT,)
    template_name = "reviews/form.html"
    form_class = ReviewForm

    def _load(self):
        self.review = get_object_or_404(
            Review.objects.select_related("request", "provider"), pk=self.kwargs["pk"], client=self.request.user
        )

    def _guard(self):
        if self.review.status == Review.Status.HIDDEN:
            messages.error(self.request, _("Cet avis a été masqué par la modération et ne peut plus être modifié."))
        elif not self.review.can_be_edited:
            messages.error(self.request, _("Un avis ne peut être modifié que pendant 48 heures après sa publication."))
        else:
            return None
        return redirect("requests_app:detail", pk=self.review.request_id)

    def get(self, request, *args, **kwargs):
        self._load()
        return self._guard() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._load()
        return self._guard() or super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.review
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(req=self.review.request, provider=self.review.provider, editing=True, review=self.review)
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("Votre avis a été modifié."))
        return redirect("requests_app:detail", pk=self.review.request_id)


class ReportView(LoginRequiredMixin, FormView):
    """Signalement d'un profil ou d'un avis (page dédiée : fonctionne sans JavaScript)."""

    template_name = "reviews/report.html"
    form_class = ReportForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.target_type, self.target = self._resolve(kwargs["target"], kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def _resolve(self, kind, pk):
        user = self.request.user
        if kind == "provider":
            provider = get_object_or_404(ProviderProfile.objects.public(), pk=pk)
            if provider.user_id == user.pk:
                raise Http404
            return Report.TargetType.PROVIDER, provider
        if kind == "review":
            review = get_object_or_404(Review.objects.select_related("provider"), pk=pk, status=Review.Status.VISIBLE)
            if review.client_id == user.pk:
                raise Http404
            return Report.TargetType.REVIEW, review
        if kind == "conversation":
            from apps.messaging.models import Conversation

            conv = get_object_or_404(Conversation.objects.select_related("provider", "client"), pk=pk)
            if user.pk not in (conv.client_id, conv.provider.user_id):
                raise Http404
            return Report.TargetType.CONVERSATION, conv
        raise Http404

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(target=self.target, target_type=self.target_type)
        return ctx

    def _back_url(self):
        if self.target_type == Report.TargetType.CONVERSATION:
            return reverse("messaging:thread", args=[self.target.pk])
        if self.target_type == Report.TargetType.PROVIDER:
            return self.target.get_absolute_url()
        return self.target.provider.get_absolute_url() + "#avis"

    def form_valid(self, form):
        already = Report.objects.filter(
            reporter=self.request.user, target_type=self.target_type, target_id=self.target.pk, status=Report.Status.PENDING
        ).exists()
        if already:
            messages.info(self.request, _("Vous avez déjà signalé ce contenu. Notre équipe l'examine."))
        else:
            report = form.save(commit=False)
            report.reporter, report.target_type, report.target_id = self.request.user, self.target_type, self.target.pk
            report.save()
            messages.success(self.request, _("Merci, votre signalement a été transmis à l'équipe Kora."))
        return redirect(self._back_url())
