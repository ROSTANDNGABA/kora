"""Catalogue : catégories, sous-catégories, champs spécifiques par métier, villes, quartiers."""
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class City(models.Model):
    name = models.CharField(_("nom"), max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    region = models.CharField(_("région"), max_length=80, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    order = models.PositiveIntegerField(_("ordre"), default=0)

    class Meta:
        verbose_name = _("ville")
        verbose_name_plural = _("villes")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Neighborhood(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="neighborhoods")
    name = models.CharField(_("nom"), max_length=80)
    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("quartier")
        verbose_name_plural = _("quartiers")
        ordering = ["city__name", "name"]
        constraints = [models.UniqueConstraint(fields=["city", "name"], name="uniq_neighborhood_per_city")]

    def __str__(self):
        return f"{self.name} ({self.city})"


class Category(models.Model):
    name = models.CharField(_("nom"), max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    icon = models.CharField(_("icône Lucide"), max_length=40, default="sparkles")
    color = models.CharField(_("couleur"), max_length=7, default="#F36F21", help_text=_("Format #RRGGBB"))
    banner = models.ImageField(_("bannière"), upload_to="categories/", blank=True)
    description = models.TextField(_("description"), blank=True)
    order = models.PositiveIntegerField(_("ordre"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("catégorie")
        verbose_name_plural = _("catégories")
        ordering = ["order", "name"]
        indexes = [models.Index(fields=["is_active", "order"])]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:category", args=[self.slug])


class Subcategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(_("nom"), max_length=80)
    slug = models.SlugField(max_length=90)
    order = models.PositiveIntegerField(_("ordre"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("sous-catégorie")
        verbose_name_plural = _("sous-catégories")
        ordering = ["category__order", "order", "name"]
        constraints = [models.UniqueConstraint(fields=["category", "slug"], name="uniq_subcategory_slug_per_category")]

    def __str__(self):
        return f"{self.category} › {self.name}"


class CategoryField(models.Model):
    """Champ spécifique à un métier, défini par l'admin (ex. « Urgence 24/7 » pour la plomberie)."""

    class FieldType(models.TextChoices):
        TEXT = "TEXT", _("Texte")
        NUMBER = "NUMBER", _("Nombre")
        CHOICE = "CHOICE", _("Choix")
        BOOLEAN = "BOOLEAN", _("Case à cocher")

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="fields")
    label = models.CharField(_("libellé"), max_length=100)
    key = models.SlugField(_("clé technique"), max_length=60)
    field_type = models.CharField(_("type"), max_length=10, choices=FieldType.choices, default=FieldType.TEXT)
    choices = models.TextField(_("choix (un par ligne)"), blank=True)
    is_required = models.BooleanField(_("obligatoire"), default=False)
    order = models.PositiveIntegerField(_("ordre"), default=0)
    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("champ de catégorie")
        verbose_name_plural = _("champs de catégorie")
        ordering = ["category__order", "order", "id"]
        constraints = [models.UniqueConstraint(fields=["category", "key"], name="uniq_field_key_per_category")]

    def __str__(self):
        return f"{self.category} · {self.label}"

    @property
    def choice_list(self):
        return [c.strip() for c in self.choices.splitlines() if c.strip()]


class SearchQuery(models.Model):
    """Trace des recherches (alimente « recherches sans résultat » du back-office)."""

    query = models.CharField(_("recherche"), max_length=120, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    results_count = models.PositiveIntegerField(_("nombre de résultats"), default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("recherche")
        verbose_name_plural = _("recherches")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["results_count", "-created_at"])]

    def __str__(self):
        return self.query or "(vide)"
