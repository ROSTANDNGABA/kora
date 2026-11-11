from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    class Type(models.TextChoices):
        REQUEST = "REQUEST", _("Demande")
        MESSAGE = "MESSAGE", _("Message")
        REVIEW = "REVIEW", _("Avis")
        ACCOUNT = "ACCOUNT", _("Compte")
        ANNOUNCEMENT = "ANNOUNCEMENT", _("Annonce")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(_("type"), max_length=14, choices=Type.choices, default=Type.ACCOUNT)
    title = models.CharField(_("titre"), max_length=140)
    body = models.TextField(_("contenu"), blank=True)
    url = models.CharField(_("lien"), max_length=300, blank=True)
    is_read = models.BooleanField(_("lue"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]

    def __str__(self):
        return f"{self.user} · {self.title}"
