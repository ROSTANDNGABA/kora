"""Logique métier des avis."""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Avg, Count

from .models import Review


def recompute_provider_rating(provider) -> None:
    """Recalcule note moyenne et nombre d'avis ; les avis masqués sont exclus (RG-04)."""
    agg = Review.objects.filter(provider=provider, status=Review.Status.VISIBLE).aggregate(
        avg=Avg("rating"), n=Count("id")
    )
    avg = Decimal(str(agg["avg"] or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    type(provider).objects.filter(pk=provider.pk).update(rating_avg=avg, reviews_count=agg["n"])
    provider.rating_avg, provider.reviews_count = avg, agg["n"]
