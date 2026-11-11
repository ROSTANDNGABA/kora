from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cms"
    label = "cms"
    verbose_name = _("Contenu")
