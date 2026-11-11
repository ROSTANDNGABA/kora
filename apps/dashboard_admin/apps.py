from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DashboardAdminConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard_admin"
    label = "dashboard_admin"
    verbose_name = _("Back-office administrateur")

    def ready(self):
        from django.db.models.signals import post_migrate

        from .permissions import ensure_groups

        post_migrate.connect(ensure_groups, sender=self)
