"""Lecture et nettoyage des filtres de recherche (GET) partagés par la recherche et les pages catégorie."""
from dataclasses import dataclass, field
from urllib.parse import urlencode

from apps.providers.selectors import SORTS

from .models import Category, City, Subcategory

MIN_RATINGS = (3, 4, 4.5)
SORT_LABELS = {
    "pertinence": "Pertinence",
    "note": "Mieux notés",
    "avis": "Plus d'avis",
    "recents": "Plus récents",
}
FILTER_KEYS = ("q", "ville", "categorie", "specialite", "note", "verifie", "prix_max", "tri")


def _to_int(value):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


@dataclass
class SearchFilters:
    q: str = ""
    city: City | None = None
    category: Category | None = None
    subcategory: Subcategory | None = None
    min_rating: float | None = None
    verified: bool = False
    max_price: int | None = None
    sort: str = "pertinence"
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_request(cls, params, fixed_category=None):
        q = (params.get("q") or "").strip()[:120]
        city = City.objects.filter(slug=params.get("ville", ""), is_active=True).first()
        category = fixed_category or Category.objects.filter(slug=params.get("categorie", ""), is_active=True).first()
        subcategory = None
        sub_slug = params.get("specialite", "")
        if sub_slug:
            qs = Subcategory.objects.filter(slug=sub_slug, is_active=True).select_related("category")
            if category:
                qs = qs.filter(category=category)
            subcategory = qs.first()
            if subcategory and not category:
                category = subcategory.category
        try:
            note = float(params.get("note", ""))
        except ValueError:
            note = None
        min_rating = note if note in MIN_RATINGS else None
        sort = params.get("tri", "")
        return cls(
            q=q, city=city, category=category, subcategory=subcategory, min_rating=min_rating,
            verified=params.get("verifie") in ("1", "on", "true"),
            max_price=_to_int(params.get("prix_max")), sort=sort if sort in SORTS else "pertinence",
        )

    @property
    def kwargs(self):
        return dict(
            q=self.q, city=self.city, category=self.category, subcategory=self.subcategory,
            min_rating=self.min_rating, verified=self.verified, max_price=self.max_price, sort=self.sort,
        )

    def query_dict(self, include_category=True):
        """Paramètres normalisés (utilisés pour les recherches enregistrées)."""
        data = {}
        if self.q:
            data["q"] = self.q
        if self.city:
            data["ville"] = self.city.slug
        if include_category and self.category:
            data["categorie"] = self.category.slug
        if self.subcategory:
            data["specialite"] = self.subcategory.slug
        if self.min_rating:
            data["note"] = f"{self.min_rating:g}"
        if self.verified:
            data["verifie"] = "1"
        if self.max_price:
            data["prix_max"] = str(self.max_price)
        if self.sort != "pertinence":
            data["tri"] = self.sort
        return data

    @property
    def query_string(self):
        return urlencode(self.query_dict())

    @property
    def active_count(self):
        """Nombre de filtres avancés actifs (pastille sur le bouton « Filtres » mobile)."""
        return sum(bool(x) for x in (self.city, self.subcategory, self.min_rating, self.verified, self.max_price))

    @property
    def label(self):
        parts = [self.q or (self.subcategory.name if self.subcategory else (self.category.name if self.category else "Tous les prestataires"))]
        if self.city:
            parts.append(f"à {self.city.name}")
        return " ".join(parts)[:120]
