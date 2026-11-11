"""Supervision des demandes, modération des avis, traitement des signalements."""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django import forms

from apps.catalog.models import Category, City
from apps.core.forms import StyledFormMixin
from apps.messaging.models import Conversation
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.providers.models import ProviderProfile
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Report, Review
from apps.reviews.services import recompute_provider_rating

from . import audit
from .exports import csv_response
from .forms import ReasonForm, RequiredReasonForm
from .models import AuditLog
from .views_base import AdminPage, ObjectAction, paginate, pick_sort

S = ServiceRequest.Status


# --- Demandes ----------------------------------------------------------------
class RequestListView(AdminPage):
    module = "requests"
    template_name = "dashboard_admin/requests.html"
    SORTS = {"created_at", "status", "updated_at"}

    def get_queryset(self):
        r = self.request.GET
        qs = ServiceRequest.objects.select_related("client", "provider", "city")
        q = r.get("q", "").strip()[:100]
        if q:
            cond = Q(description__icontains=q) | Q(client__email__icontains=q) | Q(provider__business_name__icontains=q)
            qs = qs.filter(cond | Q(pk=int(q))) if q.isdigit() else qs.filter(cond)
        if r.get("statut") in S.values:
            qs = qs.filter(status=r["statut"])
        if r.get("ville", "").isdigit():
            qs = qs.filter(city_id=r["ville"])
        if r.get("categorie", "").isdigit():
            qs = qs.filter(provider__category_id=r["categorie"])
        return qs.order_by(pick_sort(self.request, self.SORTS, "-created_at"))

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            audit.log(request, "requests.export")
            rows = ((x.pk, x.created_at.strftime("%Y-%m-%d"), x.client.email, x.provider.business_name, x.city.name, x.get_status_display(), x.budget or "") for x in self.get_queryset())
            return csv_response("demandes.csv", ["id", "date", "client", "prestataire", "ville", "statut", "budget"], rows)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(page_obj=paginate(self.request, self.get_queryset()), statuses=S.choices, categories=Category.objects.all(), cities=City.objects.all())
        return ctx


class RequestDetailView(AdminPage):
    module = "requests"
    template_name = "dashboard_admin/request_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = get_object_or_404(ServiceRequest.objects.select_related("client", "provider", "provider__user", "city"), pk=self.kwargs["pk"])
        ctx.update(
            req=req, quotes=req.quotes.all(), photos=req.photos.all(), review=getattr(req, "review", None),
            can_cancel=req.status not in (S.DONE, S.CANCELLED, S.REFUSED),
            history=AuditLog.objects.filter(entity_type="ServiceRequest", entity_id=str(req.pk))[:10],
            mediation_form=RequiredReasonForm(),
        )
        return ctx


class _RequestAction(ObjectAction):
    module = "requests"
    redirect_name = "dashboard_admin:request_detail"

    def get_queryset(self):
        return ServiceRequest.objects.select_related("client", "provider", "provider__user")


class RequestCancelView(_RequestAction):
    reason_form = RequiredReasonForm
    success = _("Demande annulée, les deux parties sont prévenues.")

    def check(self, req):
        return None if req.status not in (S.DONE, S.CANCELLED, S.REFUSED) else _("Cette demande est déjà clôturée.")

    def perform(self, request, req, reason):
        before = req.status
        req.status = S.CANCELLED
        req.save(update_fields=["status", "updated_at"])
        body = _("Demande n°%(n)d annulée par l'équipe Kora. Motif : %(reason)s") % {"n": req.pk, "reason": reason}
        notify(req.client, _("Une demande a été annulée"), body=body, url=reverse("requests_app:detail", args=[req.pk]), type=Notification.Type.REQUEST)
        notify(req.provider.user, _("Une demande a été annulée"), body=body, url=reverse("dashboard_provider:request_detail", args=[req.pk]), type=Notification.Type.REQUEST)
        audit.log(request, "request.cancel", req, {"statut": [before, S.CANCELLED], "motif": reason})


class RequestMediateView(_RequestAction):
    """Message de médiation envoyé aux deux parties (sans modifier l'état de la demande)."""

    reason_form = RequiredReasonForm
    success = _("Message de médiation envoyé au client et au prestataire.")

    def perform(self, request, req, reason):
        title = _("Message de l'équipe Kora à propos de la demande n°%(n)d") % {"n": req.pk}
        notify(req.client, title, body=reason, type=Notification.Type.ACCOUNT)
        notify(req.provider.user, title, body=reason, url=reverse("dashboard_provider:request_detail", args=[req.pk]), type=Notification.Type.ACCOUNT)
        audit.log(request, "request.mediate", req, {"message": reason})


# --- Avis --------------------------------------------------------------------
class ReviewListView(AdminPage):
    module = "reviews"
    template_name = "dashboard_admin/reviews.html"

    def get_queryset(self):
        r = self.request.GET
        reported = Report.objects.filter(target_type="REVIEW", status=Report.Status.PENDING).values("target_id")
        qs = Review.objects.select_related("client", "provider").annotate(
            pending_reports=Count("id", filter=Q(id__in=reported))
        )
        q = r.get("q", "").strip()[:100]
        if q:
            qs = qs.filter(Q(comment__icontains=q) | Q(provider__business_name__icontains=q) | Q(client__email__icontains=q))
        filtre = r.get("filtre", "")
        if filtre == "signales":
            qs = qs.filter(id__in=reported)
        elif filtre == "notes-basses":
            qs = qs.filter(rating__lte=2)
        elif filtre == "masques":
            qs = qs.filter(status=Review.Status.HIDDEN)
        elif filtre == "visibles":
            qs = qs.filter(status=Review.Status.VISIBLE)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            page_obj=paginate(self.request, self.get_queryset()), filtre=self.request.GET.get("filtre", ""),
            filters=[("", "Tous"), ("signales", "Signalés"), ("notes-basses", "Notes basses (1-2)"), ("visibles", "Visibles"), ("masques", "Masqués")],
        )
        return ctx


class _ReviewAction(ObjectAction):
    module = "reviews"
    redirect_name = "dashboard_admin:reviews"

    def get_queryset(self):
        return Review.objects.select_related("client", "provider", "provider__user")

    def redirect_args(self, obj):
        return []


class ReviewHideView(_ReviewAction):
    reason_form = RequiredReasonForm
    success = _("Avis masqué : il ne compte plus dans la note.")

    def check(self, r):
        return None if r.status == Review.Status.VISIBLE else _("Cet avis est déjà masqué.")

    def perform(self, request, r, reason):
        r.status = Review.Status.HIDDEN
        r.save(update_fields=["status", "updated_at"])
        recompute_provider_rating(r.provider)
        notify(r.client, _("Votre avis a été masqué"), body=reason, type=Notification.Type.REVIEW)
        audit.log(request, "review.hide", r, {"motif": reason, "prestataire": r.provider_id})


class ReviewRestoreView(_ReviewAction):
    success = _("Avis rétabli.")

    def check(self, r):
        return None if r.status == Review.Status.HIDDEN else _("Cet avis est déjà visible.")

    def perform(self, request, r, reason):
        r.status = Review.Status.VISIBLE
        r.save(update_fields=["status", "updated_at"])
        recompute_provider_rating(r.provider)
        notify(r.client, _("Votre avis est de nouveau visible"), type=Notification.Type.REVIEW)
        audit.log(request, "review.restore", r, {"prestataire": r.provider_id})


class ReviewDeleteView(_ReviewAction):
    reason_form = RequiredReasonForm
    success = _("Avis supprimé définitivement.")

    def perform(self, request, r, reason):
        provider, client, pk = r.provider, r.client, r.pk
        detail = {"note": r.rating, "motif": reason, "prestataire": provider.pk}
        r.delete()
        recompute_provider_rating(provider)
        notify(client, _("Votre avis a été supprimé"), body=reason, type=Notification.Type.REVIEW)
        audit.log(request, "review.delete", None, {"id": pk, **detail})


# --- Signalements ------------------------------------------------------------
def report_target(report):
    """Objet visé par un signalement (ou None s'il a été supprimé depuis)."""
    model = {"PROVIDER": ProviderProfile, "REVIEW": Review, "CONVERSATION": Conversation}[report.target_type]
    return model.objects.filter(pk=report.target_id).first()


class ReportListView(AdminPage):
    module = "reports"
    template_name = "dashboard_admin/reports.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        state = self.request.GET.get("statut", "PENDING")
        state = state if state in Report.Status.values else "PENDING"
        qs = Report.objects.filter(status=state).select_related("reporter", "handled_by")
        kind = self.request.GET.get("type", "")
        if kind in Report.TargetType.values:
            qs = qs.filter(target_type=kind)
        ctx.update(page_obj=paginate(self.request, qs), state=state, kind=kind, states=Report.Status.choices, kinds=Report.TargetType.choices)
        return ctx


class ReportDetailView(AdminPage):
    module = "reports"
    template_name = "dashboard_admin/report_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        report = get_object_or_404(Report.objects.select_related("reporter", "handled_by"), pk=self.kwargs["pk"])
        target = report_target(report)
        ctx.update(report=report, target=target, other_reports=Report.objects.filter(target_type=report.target_type, target_id=report.target_id).exclude(pk=report.pk)[:5])
        if report.target_type == "CONVERSATION" and target:
            ctx["conversation_messages"] = target.messages.select_related("sender").order_by("-created_at")[:20]
        return ctx


class ReportTreatForm(StyledFormMixin, forms.Form):
    decision = forms.ChoiceField(choices=[("resolve", "Résoudre"), ("reject", "Rejeter")])
    note = forms.CharField(max_length=400, min_length=5)
    action = forms.ChoiceField(required=False, choices=[("", ""), ("hide_review", ""), ("suspend_provider", "")])


class ReportTreatView(ObjectAction):
    """Traite un signalement : résolu (avec action éventuelle sur la cible) ou rejeté. Prévient l'auteur du signalement."""

    module = "reports"
    redirect_name = "dashboard_admin:reports"

    def get_queryset(self):
        return Report.objects.select_related("reporter")

    def redirect_args(self, obj):
        return []

    def check(self, report):
        return None if report.status == Report.Status.PENDING else _("Ce signalement a déjà été traité.")

    def post(self, request, pk):
        from django.contrib import messages
        from django.shortcuts import redirect

        report = get_object_or_404(self.get_queryset(), pk=pk)
        form = ReportTreatForm(request.POST)
        target_url = reverse("dashboard_admin:report_detail", args=[report.pk])
        if not form.is_valid():
            messages.error(request, _("Indiquez une décision et une note de traitement (5 caractères minimum)."))
            return redirect(target_url)
        if self.check(report):
            messages.error(request, self.check(report))
            return redirect(target_url)
        d = form.cleaned_data
        done = []
        target = report_target(report)
        if d["decision"] == "resolve":
            if d["action"] == "hide_review" and report.target_type == "REVIEW" and target and target.status == Review.Status.VISIBLE:
                target.status = Review.Status.HIDDEN
                target.save(update_fields=["status", "updated_at"])
                recompute_provider_rating(target.provider)
                notify(target.client, _("Votre avis a été masqué"), body=d["note"], type=Notification.Type.REVIEW)
                audit.log(request, "review.hide", target, {"motif": d["note"], "via_signalement": report.pk})
                done.append("avis masqué")
            elif d["action"] == "suspend_provider" and report.target_type == "PROVIDER" and target and target.status == ProviderProfile.Status.ACTIVE:
                target.status, target.status_reason = ProviderProfile.Status.SUSPENDED, d["note"]
                target.save(update_fields=["status", "status_reason", "updated_at"])
                notify(target.user, _("Votre profil a été suspendu"), body=d["note"], url=reverse("dashboard_provider:home"), type=Notification.Type.ACCOUNT)
                audit.log(request, "provider.suspend", target, {"motif": d["note"], "via_signalement": report.pk})
                done.append("prestataire suspendu")
        report.status = Report.Status.RESOLVED if d["decision"] == "resolve" else Report.Status.REJECTED
        report.handled_by, report.handled_at, report.resolution_note = request.user, timezone.now(), d["note"]
        report.save(update_fields=["status", "handled_by", "handled_at", "resolution_note"])
        verdict = _("Votre signalement a été examiné et traité.") if d["decision"] == "resolve" else _("Votre signalement a été examiné : aucune action n'a été jugée nécessaire.")
        notify(report.reporter, _("Suite donnée à votre signalement"), body=f"{verdict} {d['note']}", type=Notification.Type.ACCOUNT)
        audit.log(request, f"report.{d['decision']}", report, {"note": d["note"], "actions": done})
        messages.success(request, _("Signalement traité."))
        return redirect(safe_next_url(request))


def safe_next_url(request):
    return reverse("dashboard_admin:reports")
