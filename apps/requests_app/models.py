"""Demandes de service et devis."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ServiceRequest(models.Model):
    class Status(models.TextChoices):
        SENT = "SENT", _("Envoyée")
        VIEWED = "VIEWED", _("Vue")
        QUOTED = "QUOTED", _("Devis reçu")
        ACCEPTED = "ACCEPTED", _("Acceptée")
        IN_PROGRESS = "IN_PROGRESS", _("En cours")
        DONE = "DONE", _("Terminée")
        CANCELLED = "CANCELLED", _("Annulée")
        REFUSED = "REFUSED", _("Refusée")

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="service_requests")
    provider = models.ForeignKey("providers.ProviderProfile", on_delete=models.CASCADE, related_name="service_requests")
    description = models.TextField(_("description du besoin"))
    city = models.ForeignKey("catalog.City", on_delete=models.PROTECT, related_name="+")
    address = models.CharField(_("adresse / quartier"), max_length=200, blank=True)
    desired_date = models.DateField(_("date souhaitée"), null=True, blank=True)
    budget = models.PositiveIntegerField(_("budget indicatif (FCFA)"), null=True, blank=True)
    status = models.CharField(_("statut"), max_length=12, choices=Status.choices, default=Status.SENT, db_index=True)
    refusal_reason = models.CharField(_("motif de refus"), max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("demande de service")
        verbose_name_plural = _("demandes de service")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "status"]),
            models.Index(fields=["client", "status"]),
        ]

    def __str__(self):
        return f"Demande #{self.pk} · {self.client} → {self.provider}"


class RequestPhoto(models.Model):
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="requests/")

    class Meta:
        verbose_name = _("photo de demande")
        verbose_name_plural = _("photos de demande")

    def __str__(self):
        return f"Photo de la demande #{self.request_id}"


class Quote(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", _("En attente de réponse")
        ACCEPTED = "ACCEPTED", _("Accepté")
        DECLINED = "DECLINED", _("Refusé")

    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name="quotes")
    amount = models.PositiveIntegerField(_("montant (FCFA)"))
    delay_days = models.PositiveIntegerField(_("délai (jours)"), default=1)
    message = models.TextField(_("message"), blank=True)
    valid_until = models.DateField(_("valable jusqu'au"), null=True, blank=True)
    status = models.CharField(_("statut"), max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("devis")
        verbose_name_plural = _("devis")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Devis {self.amount} FCFA · demande #{self.request_id}"
