"""Mixins de permission partagés par toutes les apps."""
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.translation import gettext as _


class RoleRequiredMixin(AccessMixin):
    """Réserve une vue à certains rôles.

    - visiteur anonyme : redirigé vers la connexion ;
    - mauvais rôle : redirigé vers son propre espace avec un message
      (ou 403 si `raise_on_denied = True`).

    Exemple : `allowed_roles = (User.Role.PROVIDER,)`.
    """

    allowed_roles: tuple = ()
    raise_on_denied = False
    denied_message = _("Vous n'avez pas accès à cette page.")

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        if not user.is_active or (self.allowed_roles and user.role not in self.allowed_roles):
            if self.raise_on_denied:
                raise PermissionDenied(self.denied_message)
            messages.error(request, self.denied_message)
            return redirect(user.get_home_url())
        return super().dispatch(request, *args, **kwargs)
