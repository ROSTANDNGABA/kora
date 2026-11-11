from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Review
from .services import recompute_provider_rating


@receiver([post_save, post_delete], sender=Review)
def update_provider_rating(sender, instance, **kwargs):
    """Garde la note du prestataire à jour à chaque création, modération ou suppression d'avis."""
    recompute_provider_rating(instance.provider)
