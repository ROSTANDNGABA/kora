"""Clients, prestataires, files de validation et vérifications."""
from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.catalog.models import Category, City
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.providers.models import ProviderProfile, Verification
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Report, Review

from . import audit
from .exports import csv_response
from .forms import ProviderEditForm, ReasonForm, RequiredReasonForm
from .models import AuditLog
from .views_base import AdminPage, CrudFormView, ObjectAction, pick_sort

P = ProviderProfile.Status


# --- Clients -----------------------------------------------------------------
class ClientListView(AdminPage):
    module = "clients"
    template_name = "dashboard_admin/clients.html"
    SORTS = {"date_joined", "last_login", "email", "first_name"}

    def get_queryset(self):
        r = self.request.GET
        qs = User.objects.filter(role=User.Role.CLIENT).annotate(requests_count=Count("service_requests", distinct=True))
        q = r.get("q", "").strip()[:100]
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q))
        if r.get("statut") == "actifs":
            qs = qs.filter(is_active=True)
        elif r.get("statut") == "suspendus":
            qs = qs.filter(is_active=False)
        return qs.order_by(pick_sort(self.request, self.SORTS, "-date_joined"))

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            audit.log(request, "clients.export")
            rows = ((u.pk, u.email, u.first_name, u.last_name, u.phone or "", u.date_joined.strftime("%Y-%m-%d"), "actif" if u.is_active else "suspendu", u.requests_count) for u in self.get_queryset())
            return csv_response("clients.csv", ["id", "email", "prénom", "nom", "téléphone", "inscription", "statut", "demandes"], rows)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from .views_base import paginate

        ctx = super().get_context_data(**kwargs)
        ctx["page_obj"] = paginate(self.request, self.get_queryset())
        return ctx


class ClientDetailView(AdminPage):
    module = "clients"
    template_name = "dashboard_admin/client_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = get_object_or_404(User, pk=self.kwargs["pk"], role=User.Role.CLIENT)
        ctx.update(
            client=user, requests=ServiceRequest.objects.filter(client=user).select_related("provider")[:15],
            reviews_count=Review.objects.filter(client=user).count(), reports_made=Report.objects.filter(reporter=user).count(),
            history=AuditLog.objects.filter(entity_type="User", entity_id=str(user.pk))[:10],
        )
        return ctx


class _ClientAction(ObjectAction):
    module = "clients"
    redirect_name = "dashboard_admin:client_detail"

    def get_queryset(self):
        return User.objects.filter(role=User.Role.CLIENT)


class ClientSuspendView(_ClientAction):
    reason_form = RequiredReasonForm
    success = _("Compte suspendu.")

    def check(self, obj):
        return None if obj.is_active else _("Ce compte est déjà suspendu.")

    def perform(self, request, user, reason):
        user.is_active = False
        user.save(update_fields=["is_active"])
        notify(user, _("Votre compte a été suspendu"), body=reason, type=Notification.Type.ACCOUNT)
        audit.log(request, "client.suspend", user, {"motif": reason})


class ClientReactivateView(_ClientAction):
    success = _("Compte réactivé.")

    def check(self, obj):
        return _("Ce compte est déjà actif.") if obj.is_active else None

    def perform(self, request, user, reason):
        user.is_active = True
        user.save(update_fields=["is_active"])
        notify(user, _("Votre compte est de nouveau actif"), body=_("Vous pouvez vous reconnecter."), type=Notification.Type.ACCOUNT)
        audit.log(request, "client.reactivate", user)


class ClientDeleteView(_ClientAction):
    success = _("Compte supprimé.")

    def get_redirect(self, request, obj):
        return reverse("dashboard_admin:clients")

    def perform(self, request, user, reason):
        detail = {"email": user.email, "demandes": user.service_requests.count()}
        pk = user.pk
        user.delete()
        audit.log(request, "client.delete", None, {"id": pk, **detail})


# --- Prestataires ------------------------------------------------------------
class ProviderListView(AdminPage):
    module = "providers"
    template_name = "dashboard_admin/providers.html"
    SORTS = {"created_at", "business_name", "rating_avg", "views_count"}

    def get_queryset(self):
        r = self.request.GET
        qs = ProviderProfile.objects.select_related("user", "category", "city").annotate(requests_count=Count("service_requests", distinct=True))
        q = r.get("q", "").strip()[:100]
        if q:
            qs = qs.filter(Q(business_name__icontains=q) | Q(user__email__icontains=q) | Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(whatsapp__icontains=q))
        if r.get("statut") in {s.value for s in P}:
            qs = qs.filter(status=r["statut"])
        if r.get("categorie", "").isdigit():
            qs = qs.filter(category_id=r["categorie"])
        if r.get("ville", "").isdigit():
            qs = qs.filter(city_id=r["ville"])
        if r.get("verifie") in ("1", "0"):
            qs = qs.filter(is_verified=r["verifie"] == "1")
        if r.get("categorie_en_attente") == "1":
            qs = qs.filter(pending_category__isnull=False)
        return qs.order_by(pick_sort(self.request, self.SORTS, "-created_at"))

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            audit.log(request, "providers.export")
            rows = ((p.pk, p.business_name, p.user.email, p.category.name, p.city.name, p.get_status_display(), "oui" if p.is_verified else "non", p.rating_avg, p.reviews_count, p.created_at.strftime("%Y-%m-%d")) for p in self.get_queryset())
            return csv_response("prestataires.csv", ["id", "nom", "email", "catégorie", "ville", "statut", "vérifié", "note", "avis", "inscription"], rows)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from .views_base import paginate

        ctx = super().get_context_data(**kwargs)
        pending = ProviderProfile.objects.filter(status=P.PENDING).select_related("user", "category", "city").order_by("created_at")
        category_changes = ProviderProfile.objects.filter(pending_category__isnull=False).exclude(status=P.PENDING).select_related("category", "pending_category")
        ctx.update(
            page_obj=paginate(self.request, self.get_queryset()), pending=pending, category_changes=category_changes,
            statuses=P.choices, categories=Category.objects.all(), cities=City.objects.all(),
        )
        return ctx


class ProviderDetailView(AdminPage):
    module = "providers"
    template_name = "dashboard_admin/provider_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = get_object_or_404(ProviderProfile.objects.select_related("user", "category", "pending_category", "city"), pk=self.kwargs["pk"])
        ctx.update(
            provider=p, verifications=p.verifications.all(), requests=p.service_requests.select_related("client")[:8],
            reviews=p.reviews.select_related("client")[:5], services=p.services.all(), portfolio=p.portfolio.all()[:8],
            reports=Report.objects.filter(target_type="PROVIDER", target_id=p.pk)[:5],
            history=AuditLog.objects.filter(entity_type="ProviderProfile", entity_id=str(p.pk))[:10],
        )
        return ctx


class ProviderEditView(CrudFormView):
    module = "providers"
    model = ProviderProfile
    form_class = ProviderEditForm
    audit_name = "provider"
    heading_edit = "Modifier le prestataire"
    multipart = False

    def get_success_url(self):
        return reverse("dashboard_admin:provider_detail", args=[self.kwargs["pk"]])


class _ProviderAction(ObjectAction):
    module = "providers"
    redirect_name = "dashboard_admin:provider_detail"

    def get_queryset(self):
        return ProviderProfile.objects.select_related("user", "category", "pending_category")

    def set_status(self, request, p, status, reason, action, title, body):
        before = p.status
        p.status, p.status_reason = status, reason
        p.save(update_fields=["status", "status_reason", "updated_at"])
        notify(p.user, title, body=body, url=reverse("dashboard_provider:home"), type=Notification.Type.ACCOUNT)
        audit.log(request, action, p, {"statut": [before, status], "motif": reason})


class ProviderApproveView(_ProviderAction):
    success = _("Prestataire validé : son profil est désormais public.")

    def check(self, p):
        return None if p.status in (P.PENDING, P.REJECTED) else _("Ce profil n'est pas en attente de validation.")

    def perform(self, request, p, reason):
        self.set_status(request, p, P.ACTIVE, "", "provider.approve", _("Votre profil est validé"), _("Il est maintenant visible sur Kora. Bienvenue !"))


class ProviderRejectView(_ProviderAction):
    reason_form = RequiredReasonForm
    success = _("Inscription refusée, le prestataire a été prévenu.")

    def check(self, p):
        return None if p.status == P.PENDING else _("Seule une inscription en attente peut être refusée.")

    def perform(self, request, p, reason):
        self.set_status(request, p, P.REJECTED, reason, "provider.reject", _("Votre inscription n'a pas été retenue"), reason)


class ProviderSuspendView(_ProviderAction):
    reason_form = RequiredReasonForm
    success = _("Prestataire suspendu : son profil n'est plus visible.")

    def check(self, p):
        return None if p.status == P.ACTIVE else _("Seul un profil actif peut être suspendu.")

    def perform(self, request, p, reason):
        self.set_status(request, p, P.SUSPENDED, reason, "provider.suspend", _("Votre profil a été suspendu"), reason)


class ProviderReactivateView(_ProviderAction):
    success = _("Prestataire réactivé.")

    def check(self, p):
        return None if p.status == P.SUSPENDED else _("Ce profil n'est pas suspendu.")

    def perform(self, request, p, reason):
        self.set_status(request, p, P.ACTIVE, "", "provider.reactivate", _("Votre profil est de nouveau visible"), _("La suspension a été levée."))


class ProviderVerifiedToggleView(_ProviderAction):
    def perform(self, request, p, reason):
        p.is_verified = not p.is_verified
        p.save(update_fields=["is_verified", "updated_at"])
        title = _("Votre profil est vérifié") if p.is_verified else _("Le badge « Vérifié » a été retiré")
        notify(p.user, title, url=reverse("dashboard_provider:verification"), type=Notification.Type.ACCOUNT)
        audit.log(request, "provider.verify" if p.is_verified else "provider.unverify", p, {"is_verified": [not p.is_verified, p.is_verified]})
        self.success = _("Badge vérifié accordé.") if p.is_verified else _("Badge vérifié retiré.")


class ProviderFeaturedToggleView(_ProviderAction):
    def check(self, p):
        return None if (p.is_featured or p.status == P.ACTIVE) else _("Seul un prestataire actif peut être mis en avant.")

    def perform(self, request, p, reason):
        p.is_featured = not p.is_featured
        p.save(update_fields=["is_featured", "updated_at"])
        audit.log(request, "provider.feature" if p.is_featured else "provider.unfeature", p)
        self.success = _("Prestataire mis en avant sur l'accueil.") if p.is_featured else _("Prestataire retiré de la mise en avant.")


class CategoryChangeApproveView(_ProviderAction):
    success = _("Changement de métier validé.")

    def check(self, p):
        return None if p.pending_category_id else _("Aucune demande de changement en cours.")

    def perform(self, request, p, reason):
        old, new = p.category, p.pending_category
        p.category, p.pending_category = new, None
        p.save(update_fields=["category", "pending_category", "updated_at"])
        p.subcategories.clear()  # les spécialités de l'ancien métier ne s'appliquent plus
        notify(p.user, _("Votre changement de métier est validé"), body=_("Nouveau métier : %(name)s. Pensez à choisir vos spécialités.") % {"name": new.name}, url=reverse("dashboard_provider:profile"), type=Notification.Type.ACCOUNT)
        audit.log(request, "provider.category_approve", p, {"catégorie": [old.name, new.name]})


class CategoryChangeRejectView(_ProviderAction):
    reason_form = RequiredReasonForm
    success = _("Changement de métier refusé.")

    def check(self, p):
        return None if p.pending_category_id else _("Aucune demande de changement en cours.")

    def perform(self, request, p, reason):
        wanted = p.pending_category
        p.pending_category = None
        p.save(update_fields=["pending_category", "updated_at"])
        notify(p.user, _("Votre changement de métier est refusé"), body=reason, url=reverse("dashboard_provider:profile"), type=Notification.Type.ACCOUNT)
        audit.log(request, "provider.category_reject", p, {"demandé": wanted.name, "motif": reason})


# --- Vérifications -----------------------------------------------------------
class VerificationListView(AdminPage):
    module = "providers"
    template_name = "dashboard_admin/verifications.html"

    def get_context_data(self, **kwargs):
        from .views_base import paginate

        ctx = super().get_context_data(**kwargs)
        state = self.request.GET.get("statut", "PENDING")
        state = state if state in Verification.Status.values else "PENDING"
        qs = Verification.objects.filter(status=state).select_related("provider", "provider__user", "reviewer").order_by("created_at")
        ctx.update(page_obj=paginate(self.request, qs), state=state, states=Verification.Status.choices, reject_form=RequiredReasonForm())
        return ctx


class VerificationFileView(AdminPage):
    """Les pièces justificatives sont servies uniquement aux administrateurs autorisés."""

    module = "providers"

    def get(self, request, pk, kind):
        v = get_object_or_404(Verification, pk=pk)
        file = {"identite": v.id_document, "activite": v.activity_proof}.get(kind)
        if not file:
            raise Http404
        audit.log(request, "verification.view_file", v, {"pièce": kind})
        return FileResponse(file.open("rb"), as_attachment=False, filename=file.name.rsplit("/", 1)[-1])


class _VerificationAction(ObjectAction):
    module = "providers"
    redirect_name = "dashboard_admin:verifications"

    def get_queryset(self):
        return Verification.objects.select_related("provider", "provider__user")

    def redirect_args(self, obj):
        return []

    def check(self, v):
        return None if v.status == Verification.Status.PENDING else _("Ce dossier a déjà été traité.")


class VerificationApproveView(_VerificationAction):
    success = _("Dossier approuvé : le badge « Vérifié » est attribué.")

    def perform(self, request, v, reason):
        v.status, v.reviewer, v.reviewed_at = Verification.Status.APPROVED, request.user, timezone.now()
        v.save(update_fields=["status", "reviewer", "reviewed_at"])
        ProviderProfile.objects.filter(pk=v.provider_id).update(is_verified=True)
        notify(v.provider.user, _("Votre compte est vérifié"), body=_("Le badge « Vérifié » apparaît désormais sur votre fiche."), url=reverse("dashboard_provider:verification"), type=Notification.Type.ACCOUNT)
        audit.log(request, "verification.approve", v, {"prestataire": v.provider_id})


class VerificationRejectView(_VerificationAction):
    reason_form = RequiredReasonForm
    success = _("Dossier refusé, le prestataire a été prévenu.")

    def perform(self, request, v, reason):
        v.status, v.reviewer, v.reviewed_at, v.reason = Verification.Status.REJECTED, request.user, timezone.now(), reason
        v.save(update_fields=["status", "reviewer", "reviewed_at", "reason"])
        notify(v.provider.user, _("Votre dossier de vérification est refusé"), body=reason, url=reverse("dashboard_provider:verification"), type=Notification.Type.ACCOUNT)
        audit.log(request, "verification.reject", v, {"prestataire": v.provider_id, "motif": reason})
