"""Requêtes de lecture sur les prestataires publics."""
from django.db.models import Exists, OuterRef, Q
from django.utils.text import slugify

from .models import ProviderProfile, Service

SORTS = {
    "pertinence": ("-is_verified", "-rating_avg", "-reviews_count", "business_name"),
    "note": ("-rating_avg", "-reviews_count", "business_name"),
    "avis": ("-reviews_count", "-rating_avg", "business_name"),
    "recents": ("-created_at", "business_name"),
}


def public_cards():
    """Prestataires visibles, avec ce qu'il faut pour afficher une carte sans requêtes supplémentaires."""
    return (
        ProviderProfile.objects.public()
        .select_related("category", "city")
        .prefetch_related("subcategories")
    )


def search_providers(*, q="", city=None, category=None, subcategory=None, min_rating=None, verified=False, max_price=None, sort="pertinence"):
    """Recherche texte tolérante aux accents et à la casse.

    Le texte est comparé aux slugs (sans accents) des métiers et du prestataire, et au nom commercial
    tel quel : « couturiere » trouve « Couturières », « plombier » trouve la sous-catégorie Plombier.
    """
    qs = public_cards()
    if city:
        qs = qs.filter(city=city)
    if category:
        qs = qs.filter(category=category)
    if subcategory:
        qs = qs.filter(subcategories=subcategory)
    if min_rating:
        qs = qs.filter(rating_avg__gte=min_rating, reviews_count__gt=0)
    if verified:
        qs = qs.filter(is_verified=True)
    if max_price:
        # Au moins un service actif dont le tarif affiché ne dépasse pas le budget.
        cheap = Service.objects.filter(provider=OuterRef("pk"), is_active=True, amount__isnull=False, amount__lte=max_price)
        qs = qs.filter(Exists(cheap))
    q = (q or "").strip()
    if q:
        slug = slugify(q)
        cond = Q(business_name__icontains=q) | Q(description__icontains=q)
        if slug:
            cond |= (
                Q(slug__icontains=slug)
                | Q(category__slug__icontains=slug)
                | Q(subcategories__slug__icontains=slug)
            )
        qs = qs.filter(cond)
    return qs.distinct().order_by(*SORTS.get(sort, SORTS["pertinence"]))
