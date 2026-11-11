"""Briques communes des vues du back-office."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import FormView, TemplateView

from . import audit
from .permissions import AdminModuleMixin


def paginate(request, qs, per_page=20):
    return Paginator(qs, per_page).get_page(request.GET.get("page"))


def pick_sort(request, allowed, default):
    """Tri demandé par ?sort=champ ou ?sort=-champ, limité à une liste blanche."""
    raw = request.GET.get("sort", "")
    return raw if raw.lstrip("-") in allowed else default


class AdminPage(AdminModuleMixin, TemplateView):
    """Page de lecture d'un module."""


def safe_next(request, default):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return default


class ObjectAction(AdminModuleMixin, View):
    """Action POST sur un objet : validation du motif, contrôle métier, exécution, journal, message.

    Les sous-classes définissent `get_queryset`, `perform` (et éventuellement `check`).
    """

    http_method_names = ["post"]
    reason_form = None
    success = ""
    redirect_name = None

    def get_queryset(self):
        raise NotImplementedError

    def check(self, obj):
        """Retourne un message d'erreur si l'action est impossible dans l'état actuel, sinon None."""
        return None

    def perform(self, request, obj, reason):
        raise NotImplementedError

    def get_redirect(self, request, obj):
        return safe_next(request, reverse(self.redirect_name, args=self.redirect_args(obj)))

    def redirect_args(self, obj):
        return [obj.pk]

    def post(self, request, pk):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        target = self.get_redirect(request, obj)
        reason = ""
        if self.reason_form:
            form = self.reason_form(request.POST)
            if not form.is_valid():
                messages.error(request, form.errors["reason"][0])
                return redirect(target)
            reason = form.cleaned_data["reason"]
        error = self.check(obj)
        if error:
            messages.error(request, error)
            return redirect(target)
        self.perform(request, obj, reason)
        messages.success(request, self.success)
        return redirect(target)


class CrudFormView(AdminModuleMixin, FormView):
    """Création ou modification d'un objet avec journal d'audit. `kwargs['pk']` absent = création."""

    model = None
    template_name = "dashboard_admin/form.html"
    audit_name = ""
    list_url_name = ""
    heading_new = ""
    heading_edit = ""
    multipart = False
    delete_url_name = ""

    def get_object(self):
        if "pk" in self.kwargs:
            return get_object_or_404(self.model, pk=self.kwargs["pk"])
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.object = self.get_object()
        kwargs["instance"] = self.object
        if self.object is None:
            kwargs["initial"] = {**kwargs.get("initial", {}), **{k: v for k, v in self.request.GET.items() if k in self.initial_from_get}}
        return kwargs

    initial_from_get = ()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            object=self.object, heading=self.heading_edit if self.object else self.heading_new,
            back_url=self.get_success_url(), multipart=self.multipart,
            delete_url=reverse(self.delete_url_name, args=[self.object.pk]) if self.object and self.delete_url_name else "",
        )
        return ctx

    def get_success_url(self):
        return reverse(self.list_url_name)

    def form_valid(self, form):
        created = self.object is None
        changed = {} if created else {f: str(form.initial.get(f, "")) for f in form.changed_data}
        obj = self.object = form.save()
        audit.log(self.request, f"{self.audit_name}.{'create' if created else 'update'}", obj, {"fields": form.changed_data, "avant": changed} if not created else {})
        messages.success(self.request, "Enregistré.")
        return redirect(self.get_success_url())


class CrudDeleteView(ObjectAction):
    """Suppression avec garde-fou : un objet protégé (ex. catégorie utilisée) n'est pas supprimé."""

    model = None
    audit_name = ""
    list_url_name = ""
    success = "Supprimé."

    def get_queryset(self):
        return self.model.objects.all()

    def get_redirect(self, request, obj):
        return safe_next(request, reverse(self.list_url_name))

    def post(self, request, pk):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        target = self.get_redirect(request, obj)
        label = str(obj)
        try:
            obj.delete()
        except ProtectedError:
            messages.error(request, "Suppression impossible : cet élément est encore utilisé. Désactivez-le plutôt.")
            return redirect(target)
        audit.log(request, f"{self.audit_name}.delete", None, {"id": pk, "libellé": label})
        messages.success(request, self.success)
        return redirect(target)
