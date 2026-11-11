from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    provider = models.ForeignKey("providers.ProviderProfile", on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("favori")
        verbose_name_plural = _("favoris")
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "provider"], name="uniq_favorite_per_user_provider")]

    def __str__(self):
        return f"{self.user} ♥ {self.provider}"


class SavedSearch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_searches")
    label = models.CharField(_("libellé"), max_length=120)
    query_string = models.CharField(_("critères (query string)"), max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("recherche enregistrée")
        verbose_name_plural = _("recherches enregistrées")
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "query_string"], name="uniq_saved_search_per_user")]

    def __str__(self):
        return self.label
