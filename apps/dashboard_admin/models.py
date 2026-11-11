from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """Trace des actions sensibles : qui, quoi, quand, depuis quelle IP."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries")
    action = models.CharField(_("action"), max_length=80, db_index=True)
    entity_type = models.CharField(_("type d'entité"), max_length=60, blank=True)
    entity_id = models.CharField(_("identifiant"), max_length=40, blank=True)
    detail = models.JSONField(_("détail (avant/après)"), default=dict, blank=True)
    ip_address = models.GenericIPAddressField(_("adresse IP"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("entrée du journal d'audit")
        verbose_name_plural = _("journal d'audit")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]
        # Une permission par module du back-office (voir permissions.MODULES).
        permissions = [
            ("module_clients", "Back-office : clients"),
            ("module_providers", "Back-office : prestataires et vérifications"),
            ("module_catalog", "Back-office : catégories, villes et quartiers"),
            ("module_requests", "Back-office : demandes"),
            ("module_reviews", "Back-office : avis et modération"),
            ("module_reports", "Back-office : signalements"),
            ("module_content", "Back-office : contenu (bannières, pages, FAQ)"),
            ("module_communication", "Back-office : communication"),
            ("module_team", "Back-office : équipe et permissions"),
            ("module_audit", "Back-office : journal d'audit"),
            ("module_settings", "Back-office : paramètres"),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} · {self.actor} · {self.action}"


class Announcement(models.Model):
    """Annonce globale envoyée à tous les comptes d'une audience (une notification par destinataire)."""

    class Audience(models.TextChoices):
        ALL = "ALL", _("Tous les utilisateurs")
        CLIENTS = "CLIENTS", _("Clients")
        PROVIDERS = "PROVIDERS", _("Prestataires")

    title = models.CharField(_("titre"), max_length=140)
    body = models.TextField(_("message"), max_length=1000)
    audience = models.CharField(_("destinataires"), max_length=10, choices=Audience.choices, default=Audience.ALL)
    url = models.CharField(_("lien (facultatif)"), max_length=300, blank=True)
    recipients_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("annonce")
        verbose_name_plural = _("annonces")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
