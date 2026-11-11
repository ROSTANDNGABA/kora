from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DashboardProviderConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard_provider"
    label = "dashboard_provider"
    verbose_name = _("Espace prestataire")
