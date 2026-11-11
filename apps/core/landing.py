"""Données de la page d'accueil, calculées depuis la base."""
from django.db.models import Count, Q

from apps.accounts.models import User
from apps.catalog.models import Category, City
from apps.catalog.selectors import search_suggestions
from apps.cms.models import FAQ
from apps.providers.models import ProviderProfile
from apps.providers.selectors import public_cards
from apps.reviews.models import Review

# (libellé, texte recherché, slug de ville) : une suggestion n'est affichée que si sa ville existe et est active.
POPULAR_SEARCHES = [
    ("Plombier à Douala", "Plombier", "douala"),
    ("Couturière à Yaoundé", "Couturière", "yaounde"),
    ("Électricien à Douala", "Électricien", "douala"),
    ("Coiffeuse à Yaoundé", "Coiffeuse", "yaounde"),
    ("Pâtissier à Bafoussam", "Pâtissier", "bafoussam"),
    ("Menuisier à Yaoundé", "Menuisier", "yaounde"),
]


def landing_context() -> dict:
    cities = list(
        City.objects.filter(is_active=True).annotate(
            provider_count=Count("providers", filter=Q(providers__status=ProviderProfile.Status.ACTIVE), distinct=True)
        )
    )
    active_slugs = {c.slug for c in cities}
    visible_reviews = Review.objects.filter(status=Review.Status.VISIBLE)
    return {
        "categories": Category.objects.filter(is_active=True),
        "cities": cities,
        "suggestions": search_suggestions(),
        "popular_searches": [(l, q, c) for l, q, c in POPULAR_SEARCHES if c in active_slugs],
        "stats": {
            "providers": ProviderProfile.objects.public().count(),
            "clients": User.objects.filter(role=User.Role.CLIENT, is_active=True).count(),
            "cities": len(cities),
            "reviews": visible_reviews.count(),
        },
        "featured": public_cards().filter(is_featured=True).order_by("-rating_avg", "-reviews_count")[:6],
        "testimonials": list(
            visible_reviews.filter(rating__gte=4).exclude(comment="")
            .select_related("client", "provider")
            .order_by("-created_at")[:6]
        ),
        "faqs": FAQ.objects.filter(is_active=True)[:6],
    }
