"""Avis clients et signalements."""
from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

EDIT_WINDOW = timedelta(hours=48)


class Review(models.Model):
    class Status(models.TextChoices):
        VISIBLE = "VISIBLE", _("Visible")
        HIDDEN = "HIDDEN", _("Masqué")

    # OneToOne : un seul avis par prestation (RG-03).
    request = models.OneToOneField("requests_app.ServiceRequest", on_delete=models.CASCADE, related_name="review")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written")
    provider = models.ForeignKey("providers.ProviderProfile", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(_("note"), validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(_("commentaire"), blank=True)
    provider_reply = models.TextField(_("réponse du prestataire"), blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(_("statut de modération"), max_length=8, choices=Status.choices, default=Status.VISIBLE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("avis")
        verbose_name_plural = _("avis")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["provider", "status"])]

    def __str__(self):
        return f"{self.rating}/5 · {self.provider}"

    @property
    def editable_until(self):
        return self.created_at + EDIT_WINDOW

    @property
    def can_be_edited(self) -> bool:
        return timezone.now() <= self.editable_until


class Report(models.Model):
    class TargetType(models.TextChoices):
        PROVIDER = "PROVIDER", _("Profil prestataire")
        REVIEW = "REVIEW", _("Avis")
        CONVERSATION = "CONVERSATION", _("Conversation")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("En attente")
        RESOLVED = "RESOLVED", _("Résolu")
        REJECTED = "REJECTED", _("Rejeté")

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")
    target_type = models.CharField(_("type de cible"), max_length=14, choices=TargetType.choices)
    target_id = models.PositiveIntegerField(_("identifiant de la cible"))
    reason = models.CharField(_("motif"), max_length=120)
    details = models.TextField(_("détails"), blank=True)
    status = models.CharField(_("statut"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    resolution_note = models.TextField(_("note de traitement"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("signalement")
        verbose_name_plural = _("signalements")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self):
        return f"Signalement {self.get_target_type_display()} #{self.target_id}"
