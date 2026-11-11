"""Enregistrement des évènements de fréquentation d'un prestataire."""
from django.db.models import F
from django.utils import timezone

from .models import ProviderDailyStat, ProviderProfile

FIELDS = {"views": "views_count", "whatsapp_clicks": "whatsapp_clicks"}


def record_event(provider_id, field):
    """Incrémente le compteur global et celui du jour (créé au besoin), de façon atomique."""
    ProviderProfile.objects.filter(pk=provider_id).update(**{FIELDS[field]: F(FIELDS[field]) + 1})
    today = timezone.localdate()
    _stat, created = ProviderDailyStat.objects.get_or_create(provider_id=provider_id, date=today, defaults={field: 1})
    if not created:
        ProviderDailyStat.objects.filter(provider_id=provider_id, date=today).update(**{field: F(field) + 1})
