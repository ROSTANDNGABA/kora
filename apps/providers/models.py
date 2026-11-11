"""Profils prestataires, services, portfolio, disponibilités, vérification."""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.storage import private_storage


class ProviderQuerySet(models.QuerySet):
    def public(self):
        """Seuls les prestataires ACTIFS sont visibles publiquement (RG-01, RG-06)."""
        return self.filter(status=ProviderProfile.Status.ACTIVE, user__is_active=True)


class ProviderProfile(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", _("En attente")
        ACTIVE = "ACTIVE", _("Actif")
        SUSPENDED = "SUSPENDED", _("Suspendu")
        REJECTED = "REJECTED", _("Refusé")

    class ActivityType(models.TextChoices):
        FREELANCE = "FREELANCE", _("Indépendant")
        WORKSHOP = "WORKSHOP", _("Atelier")
        COMPANY = "COMPANY", _("Entreprise")

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="provider_profile")
    business_name = models.CharField(_("nom commercial"), max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    activity_type = models.CharField(_("type d'activité"), max_length=10, choices=ActivityType.choices, default=ActivityType.FREELANCE)
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="providers")
    pending_category = models.ForeignKey(
        "catalog.Category", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text=_("Changement de catégorie principale en attente de validation admin."),
    )
    subcategories = models.ManyToManyField("catalog.Subcategory", blank=True, related_name="providers")
    description = models.TextField(_("description"), blank=True)
    logo = models.ImageField(_("logo / photo"), upload_to="providers/", blank=True)
    city = models.ForeignKey("catalog.City", on_delete=models.PROTECT, related_name="providers")
    neighborhoods = models.ManyToManyField("catalog.Neighborhood", blank=True, related_name="providers")
    whatsapp = models.CharField(_("WhatsApp"), max_length=20)
    show_phone_publicly = models.BooleanField(_("afficher mon numéro publiquement"), default=False)
    home_service = models.BooleanField(_("intervention à domicile"), default=False)
    is_unavailable = models.BooleanField(_("indisponible / en congés"), default=False)

    status = models.CharField(_("statut"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    status_reason = models.TextField(_("motif (refus / suspension)"), blank=True)
    is_verified = models.BooleanField(_("vérifié"), default=False)
    is_featured = models.BooleanField(_("mis en avant"), default=False)

    rating_avg = models.DecimalField(_("note moyenne"), max_digits=3, decimal_places=2, default=0)
    reviews_count = models.PositiveIntegerField(_("nombre d'avis"), default=0)
    views_count = models.PositiveIntegerField(_("vues du profil"), default=0)
    whatsapp_clicks = models.PositiveIntegerField(_("clics WhatsApp"), default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProviderQuerySet.as_manager()

    class Meta:
        verbose_name = _("prestataire")
        verbose_name_plural = _("prestataires")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "category"]),
            models.Index(fields=["status", "city"]),
            models.Index(fields=["status", "-rating_avg"]),
            models.Index(fields=["is_featured", "status"]),
        ]

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.business_name) or "prestataire"
            slug, i = base, 2
            while ProviderProfile.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f"{base}-{i}", i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("providers:detail", args=[self.slug])

    @property
    def main_trade(self) -> str:
        """Libellé du métier affiché sur les cartes : première spécialité, sinon la catégorie."""
        subs = list(self.subcategories.all())  # prefetch_related évite une requête par carte
        return subs[0].name if subs else self.category.name

    @property
    def is_public(self) -> bool:
        return self.status == self.Status.ACTIVE and self.user.is_active


class ProviderFieldValue(models.Model):
    """Valeur saisie par un prestataire pour un champ défini par l'admin sur sa catégorie."""

    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="field_values")
    field = models.ForeignKey("catalog.CategoryField", on_delete=models.CASCADE, related_name="values")
    value = models.TextField(blank=True)

    class Meta:
        verbose_name = _("valeur de champ")
        verbose_name_plural = _("valeurs de champs")
        constraints = [models.UniqueConstraint(fields=["provider", "field"], name="uniq_value_per_provider_field")]

    def __str__(self):
        return f"{self.provider} · {self.field.label}"


class Service(models.Model):
    class PriceType(models.TextChoices):
        FIXED = "FIXED", _("Prix fixe")
        FROM = "FROM", _("À partir de")
        QUOTE = "QUOTE", _("Sur devis")

    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="services")
    title = models.CharField(_("titre"), max_length=120)
    description = models.TextField(_("description"), blank=True)
    price_type = models.CharField(_("type de prix"), max_length=6, choices=PriceType.choices, default=PriceType.FIXED)
    amount = models.PositiveIntegerField(_("montant (FCFA)"), null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(_("durée estimée (min)"), null=True, blank=True)
    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("service")
        verbose_name_plural = _("services")
        ordering = ["provider", "id"]

    def __str__(self):
        return f"{self.title} ({self.provider})"


class PortfolioMedia(models.Model):
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="portfolio")
    image = models.ImageField(_("image"), upload_to="portfolio/")
    caption = models.CharField(_("légende"), max_length=160, blank=True)
    order = models.PositiveIntegerField(_("ordre"), default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("média du portfolio")
        verbose_name_plural = _("médias du portfolio")
        ordering = ["provider", "order", "id"]

    def __str__(self):
        return f"{self.provider} · {self.caption or self.pk}"


class Availability(models.Model):
    class Weekday(models.IntegerChoices):
        MON = 0, _("Lundi")
        TUE = 1, _("Mardi")
        WED = 2, _("Mercredi")
        THU = 3, _("Jeudi")
        FRI = 4, _("Vendredi")
        SAT = 5, _("Samedi")
        SUN = 6, _("Dimanche")

    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="availabilities")
    weekday = models.PositiveSmallIntegerField(_("jour"), choices=Weekday.choices)
    opens_at = models.TimeField(_("ouverture"), null=True, blank=True)
    closes_at = models.TimeField(_("fermeture"), null=True, blank=True)
    is_closed = models.BooleanField(_("fermé"), default=False)

    class Meta:
        verbose_name = _("disponibilité")
        verbose_name_plural = _("disponibilités")
        ordering = ["provider", "weekday"]
        constraints = [models.UniqueConstraint(fields=["provider", "weekday"], name="uniq_availability_per_day")]

    def __str__(self):
        return f"{self.provider} · {self.get_weekday_display()}"


class Verification(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", _("En attente")
        APPROVED = "APPROVED", _("Approuvée")
        REJECTED = "REJECTED", _("Refusée")

    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="verifications")
    id_document = models.FileField(_("pièce d'identité"), upload_to="verifications/", storage=private_storage)
    activity_proof = models.FileField(_("preuve d'activité"), upload_to="verifications/", storage=private_storage, blank=True)
    status = models.CharField(_("statut"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    reason = models.TextField(_("motif"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("vérification")
        verbose_name_plural = _("vérifications")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider} · {self.get_status_display()}"


class ProviderDailyStat(models.Model):
    """Compteurs quotidiens (vues du profil, clics WhatsApp) pour les graphiques et statistiques."""

    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="daily_stats")
    date = models.DateField(db_index=True)
    views = models.PositiveIntegerField(default=0)
    whatsapp_clicks = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("statistique quotidienne")
        verbose_name_plural = _("statistiques quotidiennes")
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["provider", "date"], name="uniq_daily_stat_per_provider")]

    def __str__(self):
        return f"{self.provider} · {self.date}"
