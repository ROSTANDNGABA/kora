"""Permissions par module du back-office.

Chaque module correspond à une permission Django `dashboard_admin.module_<nom>`. Les groupes ci-dessous sont
recréés à chaque migration (signal post_migrate) pour que l'équipe dispose de rôles prêts à l'emploi.
Le superutilisateur a tous les modules.
"""
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.accounts.models import User
from apps.core.mixins import RoleRequiredMixin

MODULES = {
    "clients": "Clients",
    "providers": "Prestataires et vérifications",
    "catalog": "Catégories, villes et quartiers",
    "requests": "Demandes",
    "reviews": "Avis et modération",
    "reports": "Signalements",
    "content": "Contenu",
    "communication": "Communication",
    "team": "Équipe et permissions",
    "audit": "Journal d'audit",
    "settings": "Paramètres",
}

GROUPS = {
    "Administrateur complet": list(MODULES),
    "Modérateur": ["providers", "reviews", "reports", "content"],
    "Support": ["clients", "requests", "reports", "communication"],
}


def can_access_module(user, module):
    if not (user.is_authenticated and user.is_active and getattr(user, "role", "") == User.Role.ADMIN):
        return False
    return user.is_superuser or user.has_perm(f"dashboard_admin.module_{module}")


def ensure_groups(**kwargs):
    from django.contrib.auth.models import Group, Permission

    perms = {p.codename: p for p in Permission.objects.filter(content_type__app_label="dashboard_admin", codename__startswith="module_")}
    if len(perms) < len(MODULES):
        return
    for name, modules in GROUPS.items():
        group, _created = Group.objects.get_or_create(name=name)
        if _created:  # on ne réécrase pas les réglages faits ensuite depuis l'interface
            group.permissions.set([perms[f"module_{m}"] for m in modules])


class AdminModuleMixin(RoleRequiredMixin):
    """Vue réservée aux administrateurs ayant accès au module `module`.

    Un client ou un prestataire est renvoyé vers son propre espace ; un administrateur sans droit sur le module reçoit un 403.
    """

    allowed_roles = (User.Role.ADMIN,)
    module = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_active and request.user.role == User.Role.ADMIN:
            if self.module and not can_access_module(request.user, self.module):
                raise PermissionDenied("Vous n'avez pas accès à ce module.")
        return super().dispatch(request, *args, **kwargs)
