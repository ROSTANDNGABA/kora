"""Utilisateur personnalisé : identifiant e-mail, téléphone optionnel, rôle."""
import re

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _


def normalize_phone(raw: str) -> str:
    """Garde uniquement les chiffres et un éventuel « + » initial."""
    raw = (raw or "").strip()
    plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    return f"+{digits}" if plus else digits


def validate_phone(value: str) -> None:
    digits = re.sub(r"\D", "", value or "")
    if not 8 <= len(digits) <= 15:
        raise ValidationError(_("Entrez un numéro de téléphone valide."))


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError(_("L'adresse e-mail est obligatoire."))
        email = self.normalize_email(email).lower()
        if extra.get("phone"):
            extra["phone"] = normalize_phone(extra["phone"])
        else:
            extra["phone"] = None
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("role", User.Role.CLIENT)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.ADMIN)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError(_("Un superutilisateur doit avoir is_staff et is_superuser à True."))
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Compte Kora. Le rôle détermine l'espace auquel l'utilisateur accède."""

    class Role(models.TextChoices):
        CLIENT = "CLIENT", _("Client")
        PROVIDER = "PROVIDER", _("Prestataire")
        ADMIN = "ADMIN", _("Administrateur")

    username = None
    email = models.EmailField(_("adresse e-mail"), unique=True)
    role = models.CharField(_("rôle"), max_length=10, choices=Role.choices, default=Role.CLIENT, db_index=True)
    phone = models.CharField(
        _("téléphone"), max_length=20, unique=True, null=True, blank=True, validators=[validate_phone]
    )
    avatar = models.ImageField(_("photo de profil"), upload_to="avatars/", blank=True)
    language = models.CharField(_("langue"), max_length=5, choices=[("fr", "Français"), ("en", "English")], default="fr")
    phone_verified = models.BooleanField(_("téléphone vérifié"), default=False)
    email_verified = models.BooleanField(_("e-mail vérifié"), default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")
        indexes = [models.Index(Lower("email"), name="user_email_lower_idx")]

    def __str__(self):
        return self.get_full_name() or self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").lower()
        self.phone = normalize_phone(self.phone) or None
        super().save(*args, **kwargs)

    @property
    def public_name(self) -> str:
        """Nom affiché publiquement (avis, témoignages) : prénom + initiale du nom."""
        first, last = (self.first_name or "").strip(), (self.last_name or "").strip()
        if not first and not last:
            return str(_("Client Kora"))
        return f"{first} {last[:1]}.".strip() if last else first

    # --- Rôles --------------------------------------------------------------
    @property
    def is_client(self) -> bool:
        return self.role == self.Role.CLIENT

    @property
    def is_provider(self) -> bool:
        return self.role == self.Role.PROVIDER

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    def get_home_url(self) -> str:
        """Page d'arrivée selon le rôle."""
        names = {
            self.Role.CLIENT: "core:client_home",
            self.Role.PROVIDER: "dashboard_provider:home",
            self.Role.ADMIN: "dashboard_admin:home",
        }
        try:
            return reverse(names[self.role])
        except NoReverseMatch:
            return reverse("core:home")


class ClientProfile(models.Model):
    """Informations complémentaires d'un client."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="client_profile")
    city = models.ForeignKey("catalog.City", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    address = models.CharField(_("adresse par défaut"), max_length=200, blank=True)
    notify_email = models.BooleanField(_("notifications par e-mail"), default=True)
    notify_sms = models.BooleanField(_("notifications par SMS"), default=False)

    class Meta:
        verbose_name = _("profil client")
        verbose_name_plural = _("profils clients")

    def __str__(self):
        return f"Profil de {self.user}"


class OTPCode(models.Model):
    """Code à usage unique de vérification (e-mail ou SMS). Le code est stocké haché."""

    class Channel(models.TextChoices):
        EMAIL = "email", _("E-mail")
        SMS = "sms", _("SMS")

    MAX_ATTEMPTS = 5
    LIFETIME_MINUTES = 10

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_codes")
    channel = models.CharField(max_length=5, choices=Channel.choices)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = _("code de vérification")
        verbose_name_plural = _("codes de vérification")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "channel", "is_used"])]

    def __str__(self):
        return f"OTP {self.channel} · {self.user}"
