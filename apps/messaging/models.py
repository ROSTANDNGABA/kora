from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Conversation(models.Model):
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations")
    provider = models.ForeignKey("providers.ProviderProfile", on_delete=models.CASCADE, related_name="conversations")
    request = models.ForeignKey("requests_app.ServiceRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("conversation")
        verbose_name_plural = _("conversations")
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["client", "provider"], name="uniq_conversation_client_provider")]

    def __str__(self):
        return f"{self.client} ↔ {self.provider}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    body = models.TextField(_("message"), blank=True)
    attachment = models.ImageField(_("pièce jointe"), upload_to="messages/", blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("message")
        verbose_name_plural = _("messages")
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"]), models.Index(fields=["conversation", "read_at"])]

    def __str__(self):
        return f"{self.sender}: {self.body[:40]}"
