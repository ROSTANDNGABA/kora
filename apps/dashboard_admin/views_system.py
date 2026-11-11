"""Équipe et permissions, journal d'audit, paramètres du site."""
from django.contrib import messages
from django.contrib.auth.models import Group
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import FormView

from apps.accounts.models import User
from apps.core.models import SiteSettings

from . import audit
from .exports import csv_response
from .forms import SiteSettingsForm, TeamMemberForm
from .models import AuditLog
from .permissions import GROUPS, MODULES, AdminModuleMixin
from .views_base import AdminPage, ObjectAction, paginate


class TeamView(AdminPage):
    module = "team"
    template_name = "dashboard_admin/team.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["members"] = User.objects.filter(role=User.Role.ADMIN).prefetch_related("groups").order_by("-is_superuser", "email")
        ctx["groups"] = Group.objects.prefetch_related("permissions")
        ctx["modules"] = MODULES
        return ctx


class TeamFormView(AdminModuleMixin, FormView):
    module = "team"
    form_class = TeamMemberForm
    template_name = "dashboard_admin/team_form.html"

    def get_member(self):
        if "pk" in self.kwargs:
            return get_object_or_404(User, pk=self.kwargs["pk"], role=User.Role.ADMIN)
        return None

    def dispatch(self, request, *args, **kwargs):
        self.member = self.get_member() if request.user.is_authenticated else None
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["member"] = self.member
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(member=self.member, group_modules={g.pk: [MODULES[m] for m in GROUPS.get(g.name, [])] for g in Group.objects.all()})
        return ctx

    def form_valid(self, form):
        d, actor = form.cleaned_data, self.request.user
        member = self.member
        if member and member.is_superuser and not actor.is_superuser:
            messages.error(self.request, "Seul un super-administrateur peut modifier ce compte.")
            return redirect("dashboard_admin:team")
        if member and member.pk == actor.pk and not d["is_active"]:
            messages.error(self.request, "Vous ne pouvez pas désactiver votre propre compte.")
            return self.form_invalid(form)
        if member:
            before = {"rôles": sorted(g.name for g in member.groups.all()), "actif": member.is_active}
            member.first_name, member.last_name, member.is_active = d["first_name"], d["last_name"], d["is_active"]
            if d["password"]:
                member.set_password(d["password"])
            member.save()
            action = "team.update"
        else:
            member = User.objects.create_user(d["email"], d["password"], role=User.Role.ADMIN, first_name=d["first_name"], last_name=d["last_name"], is_staff=True, is_active=d["is_active"])
            before, action = {}, "team.create"
        if not (member.pk == actor.pk and not actor.is_superuser):  # on ne modifie pas ses propres rôles
            member.groups.set(d["groups"])
        audit.log(self.request, action, member, {"avant": before, "rôles": sorted(g.name for g in d["groups"]), "mot_de_passe_changé": bool(d["password"])})
        messages.success(self.request, "Membre enregistré.")
        return redirect("dashboard_admin:team")


class TeamToggleView(ObjectAction):
    module = "team"
    redirect_name = "dashboard_admin:team"

    def get_queryset(self):
        return User.objects.filter(role=User.Role.ADMIN)

    def redirect_args(self, obj):
        return []

    def check(self, member):
        return "Vous ne pouvez pas désactiver votre propre compte." if member.pk == self.request.user.pk else None

    def post(self, request, pk):
        self.request = request
        member = get_object_or_404(self.get_queryset(), pk=pk)
        if member.is_superuser and not request.user.is_superuser:
            messages.error(request, "Seul un super-administrateur peut modifier ce compte.")
            return redirect("dashboard_admin:team")
        return super().post(request, pk)

    def perform(self, request, member, reason):
        member.is_active = not member.is_active
        member.save(update_fields=["is_active"])
        audit.log(request, "team.activate" if member.is_active else "team.deactivate", member)
        self.success = "Compte réactivé." if member.is_active else "Compte désactivé."


class AuditView(AdminPage):
    module = "audit"
    template_name = "dashboard_admin/audit.html"

    def get_queryset(self):
        r = self.request.GET
        qs = AuditLog.objects.select_related("actor")
        if r.get("acteur", "").isdigit():
            qs = qs.filter(actor_id=r["acteur"])
        if r.get("action"):
            qs = qs.filter(action__startswith=r["action"][:40])
        if r.get("entite"):
            qs = qs.filter(entity_type=r["entite"][:60])
        if r.get("du"):
            qs = qs.filter(created_at__date__gte=r["du"][:10]) if _is_date(r["du"]) else qs
        if r.get("au"):
            qs = qs.filter(created_at__date__lte=r["au"][:10]) if _is_date(r["au"]) else qs
        q = r.get("q", "").strip()[:100]
        if q:
            qs = qs.filter(Q(action__icontains=q) | Q(entity_id=q) | Q(actor__email__icontains=q) | Q(ip_address=q if _is_ip(q) else None))
        return qs

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            audit.log(request, "audit.export")
            rows = ((e.created_at.strftime("%Y-%m-%d %H:%M:%S"), e.actor.email if e.actor else "", e.action, e.entity_type, e.entity_id, e.ip_address or "", e.detail) for e in self.get_queryset()[:5000])
            return csv_response("journal-audit.csv", ["date", "acteur", "action", "entité", "id", "ip", "détail"], rows)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            page_obj=paginate(self.request, self.get_queryset(), 30),
            actors=User.objects.filter(audit_entries__isnull=False).distinct().order_by("email"),
            entities=AuditLog.objects.exclude(entity_type="").values_list("entity_type", flat=True).distinct().order_by("entity_type"),
        )
        return ctx


def _is_date(value):
    from datetime import date

    try:
        date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


def _is_ip(value):
    import ipaddress

    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


class SettingsView(AdminModuleMixin, FormView):
    module = "settings"
    form_class = SiteSettingsForm
    template_name = "dashboard_admin/settings.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = SiteSettings.objects.filter(pk=1).first() or SiteSettings()
        return kwargs

    def form_valid(self, form):
        form.save()
        audit.log(self.request, "settings.update", None, {"champs": form.changed_data})
        messages.success(self.request, "Paramètres enregistrés.")
        return redirect("dashboard_admin:settings")
