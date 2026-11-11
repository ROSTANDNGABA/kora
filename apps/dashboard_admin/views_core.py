"""Tableau de bord, recherche globale."""
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import User
from apps.providers.models import ProviderProfile, Verification
from apps.requests_app.models import ServiceRequest
from apps.reviews.models import Report, Review

from .counts import admin_badges
from .exports import csv_response
from .models import AuditLog
from .permissions import can_access_module
from .views_base import AdminPage

P = ProviderProfile.Status


def _daily(qs, field, days):
    start = timezone.localdate() - timedelta(days=days - 1)
    found = dict(qs.filter(**{f"{field}__date__gte": start}).annotate(d=TruncDate(field)).values_list("d").annotate(n=Count("id")).order_by())
    return [{"date": (start + timedelta(days=i)).strftime("%d/%m"), "n": found.get(start + timedelta(days=i), 0)} for i in range(days)]


def dashboard_data():
    now = timezone.now()
    since = now - timedelta(days=30)
    status_labels = dict(ServiceRequest.Status.choices)
    return {
        "kpi": {
            "clients": User.objects.filter(role=User.Role.CLIENT).count(),
            "clients_new": User.objects.filter(role=User.Role.CLIENT, date_joined__gte=since).count(),
            "providers_active": ProviderProfile.objects.filter(status=P.ACTIVE).count(),
            "providers_total": ProviderProfile.objects.count(),
            "requests_30": ServiceRequest.objects.filter(created_at__gte=since).count(),
            "requests_total": ServiceRequest.objects.count(),
            "reviews": Review.objects.filter(status=Review.Status.VISIBLE).count(),
            "done_30": ServiceRequest.objects.filter(status=ServiceRequest.Status.DONE, completed_at__gte=since).count(),
        },
        "badges": admin_badges(),
        "signups": [
            {"date": a["date"], "clients": a["n"], "providers": b["n"]}
            for a, b in zip(_daily(User.objects.filter(role=User.Role.CLIENT), "date_joined", 30), _daily(ProviderProfile.objects.all(), "created_at", 30))
        ],
        "by_category": [{"label": r["category__name"], "n": r["n"]} for r in ProviderProfile.objects.filter(status=P.ACTIVE).values("category__name").annotate(n=Count("id")).order_by("-n")],
        "by_city": [{"label": r["city__name"], "n": r["n"]} for r in ProviderProfile.objects.filter(status=P.ACTIVE).values("city__name").annotate(n=Count("id")).order_by("-n")[:8]],
        "by_status": [{"label": status_labels[r["status"]], "n": r["n"]} for r in ServiceRequest.objects.values("status").annotate(n=Count("id")).order_by("-n")],
    }


class HomeView(AdminPage):
    template_name = "dashboard_admin/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        data = dashboard_data()
        user = self.request.user
        ctx.update(data)
        ctx["chart"] = {k: data[k] for k in ("signups", "by_category", "by_city", "by_status")}
        ctx["recent_signups"] = User.objects.exclude(role=User.Role.ADMIN).order_by("-date_joined")[:6]
        ctx["recent_activity"] = AuditLog.objects.select_related("actor")[:8] if can_access_module(user, "audit") else []
        ctx["can_audit"] = can_access_module(user, "audit")
        return ctx

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            from . import audit

            audit.log(request, "dashboard.export")
            k = dashboard_data()["kpi"]
            labels = {"clients": "Clients", "clients_new": "Nouveaux clients (30 j)", "providers_active": "Prestataires actifs", "providers_total": "Prestataires (total)", "requests_30": "Demandes (30 j)", "requests_total": "Demandes (total)", "reviews": "Avis visibles", "done_30": "Prestations terminées (30 j)"}
            return csv_response("kora-indicateurs.csv", ["indicateur", "valeur"], [(labels[key], v) for key, v in k.items()])
        return super().get(request, *args, **kwargs)


class SearchView(AdminPage):
    """Recherche globale de la barre du haut : comptes, prestataires et demandes (selon les droits)."""

    template_name = "dashboard_admin/search.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "").strip()[:100]
        user = self.request.user
        results = {}
        if len(q) >= 2:
            if can_access_module(user, "clients"):
                results["clients"] = User.objects.filter(role=User.Role.CLIENT).filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q))[:8]
            if can_access_module(user, "providers"):
                results["providers"] = ProviderProfile.objects.select_related("category", "city").filter(Q(business_name__icontains=q) | Q(user__email__icontains=q) | Q(whatsapp__icontains=q))[:8]
            if can_access_module(user, "requests"):
                cond = Q(description__icontains=q)
                if q.isdigit():
                    cond |= Q(pk=int(q))
                results["requests"] = ServiceRequest.objects.select_related("client", "provider").filter(cond)[:8]
        ctx.update(q=q, results=results, total=sum(len(list(v)) for v in results.values()))
        return ctx
