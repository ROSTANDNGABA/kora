"""Réglages généraux du site (une seule ligne), modifiables depuis le back-office."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class SiteSettings(models.Model):
    site_slogan = models.CharField(_("slogan"), max_length=160, blank=True, help_text=_("Laisser vide pour garder le slogan par défaut."))
    support_whatsapp = models.CharField(_("WhatsApp du support"), max_length=20, blank=True, help_text=_("Format international sans +, ex. 237600000000."))
    contact_email = models.EmailField(_("e-mail de contact"), blank=True)
    upload_max_mb = models.PositiveSmallIntegerField(_("poids maximum d'une image (Mo)"), default=5, validators=[MinValueValidator(1), MaxValueValidator(20)])
    portfolio_max_items = models.PositiveSmallIntegerField(_("photos maximum par portfolio"), default=20, validators=[MinValueValidator(1), MaxValueValidator(100)])

    class Meta:
        verbose_name = _("réglages du site")
        verbose_name_plural = _("réglages du site")

    def __str__(self):
        return "Réglages du site"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        from . import site_settings

        site_settings.clear_cache()
