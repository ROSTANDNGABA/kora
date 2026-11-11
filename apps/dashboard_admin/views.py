from django.views.generic import TemplateView

from apps.accounts.models import User
from apps.core.mixins import RoleRequiredMixin
from apps.providers.models import ProviderProfile


class HomeView(RoleRequiredMixin, TemplateView):
    """Accueil du back-office (le tableau de bord complet arrive en phase 6)."""

    allowed_roles = (User.Role.ADMIN,)
    template_name = "dashboard_admin/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pending_providers"] = ProviderProfile.objects.filter(status=ProviderProfile.Status.PENDING).count()
        ctx["clients"] = User.objects.filter(role=User.Role.CLIENT).count()
        ctx["providers"] = ProviderProfile.objects.count()
        return ctx
