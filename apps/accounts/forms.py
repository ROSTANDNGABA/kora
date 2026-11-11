from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import Category, City, Subcategory
from apps.core.forms import StyledFormMixin
from apps.providers.models import ProviderProfile

from .models import User, normalize_phone, validate_phone


class LoginForm(AuthenticationForm):
    """Connexion avec e-mail ou téléphone."""

    username = forms.CharField(
        label=_("E-mail ou téléphone"),
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username", "class": "input"}),
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "class": "input"}),
    )
    error_messages = {
        "invalid_login": _("Identifiants incorrects. Vérifiez votre e-mail ou téléphone et votre mot de passe."),
        "inactive": _("Ce compte est désactivé."),
    }


class BaseSignupForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(label=_("Prénom"), max_length=150)
    last_name = forms.CharField(label=_("Nom"), max_length=150)
    email = forms.EmailField(label=_("Adresse e-mail"))
    password1 = forms.CharField(label=_("Mot de passe"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label=_("Confirmer le mot de passe"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    accept_terms = forms.BooleanField(
        label=_("J'accepte les conditions générales d'utilisation et la politique de confidentialité"),
        error_messages={"required": _("Vous devez accepter les conditions pour créer un compte.")},
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("Un compte existe déjà avec cette adresse e-mail."))
        return email

    def clean_phone(self):
        raw = self.cleaned_data.get("phone", "")
        if not raw:
            return None
        validate_phone(raw)
        phone = normalize_phone(raw)
        if User.objects.filter(phone=phone).exists():
            raise ValidationError(_("Un compte existe déjà avec ce numéro de téléphone."))
        return phone

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("Les deux mots de passe ne correspondent pas."))
        elif p1:
            candidate = User(email=cleaned.get("email", ""), first_name=cleaned.get("first_name", ""), last_name=cleaned.get("last_name", ""))
            try:
                password_validation.validate_password(p1, candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class ClientSignupForm(BaseSignupForm):
    phone = forms.CharField(label=_("Téléphone (optionnel)"), required=False, max_length=20)
    city = forms.ModelChoiceField(label=_("Ville"), queryset=City.objects.none(), required=False, empty_label=_("Choisir une ville"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.filter(is_active=True)


class ProviderSignupForm(BaseSignupForm):
    business_name = forms.CharField(label=_("Nom de votre activité"), max_length=120)
    activity_type = forms.ChoiceField(label=_("Statut"), choices=ProviderProfile.ActivityType.choices)
    category = forms.ModelChoiceField(label=_("Votre métier (catégorie)"), queryset=Category.objects.none(), empty_label=_("Choisir un métier"))
    subcategories = forms.ModelMultipleChoiceField(
        label=_("Spécialités"), queryset=Subcategory.objects.none(), widget=forms.CheckboxSelectMultiple,
        error_messages={"required": _("Choisissez au moins une spécialité.")},
    )
    city = forms.ModelChoiceField(label=_("Ville"), queryset=City.objects.none(), empty_label=_("Choisir une ville"))
    whatsapp = forms.CharField(label=_("Numéro WhatsApp"), max_length=20, help_text=_("Utilisé aussi pour vous connecter et vous joindre."))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        self.fields["subcategories"].queryset = Subcategory.objects.filter(is_active=True, category__is_active=True)

    def clean_whatsapp(self):
        raw = self.cleaned_data["whatsapp"]
        validate_phone(raw)
        phone = normalize_phone(raw)
        if User.objects.filter(phone=phone).exists():
            raise ValidationError(_("Un compte existe déjà avec ce numéro."))
        return phone

    def clean(self):
        cleaned = super().clean()
        category, subs = cleaned.get("category"), cleaned.get("subcategories")
        if category and subs and any(s.category_id != category.id for s in subs):
            self.add_error("subcategories", _("Les spécialités doivent appartenir au métier choisi."))
        return cleaned


class OTPForm(StyledFormMixin, forms.Form):
    code = forms.CharField(
        label=_("Code à 6 chiffres"), min_length=6, max_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "pattern": "[0-9]{6}", "autofocus": True}),
    )


MAX_AVATAR_MB = 3


class ClientProfileForm(StyledFormMixin, forms.Form):
    """Informations personnelles du client (compte + profil client)."""

    first_name = forms.CharField(label=_("Prénom"), max_length=150)
    last_name = forms.CharField(label=_("Nom"), max_length=150)
    phone = forms.CharField(label=_("Téléphone"), required=False, max_length=20)
    avatar = forms.ImageField(label=_("Photo de profil"), required=False, widget=forms.FileInput(attrs={"accept": "image/*", "class": "block w-full text-sm"}))
    remove_avatar = forms.BooleanField(label=_("Supprimer ma photo"), required=False)
    language = forms.ChoiceField(label=_("Langue"), choices=[("fr", "Français"), ("en", "English")])
    city = forms.ModelChoiceField(label=_("Ville"), queryset=City.objects.none(), required=False, empty_label=_("Non renseignée"))
    address = forms.CharField(label=_("Adresse par défaut"), required=False, max_length=200)
    notify_email = forms.BooleanField(label=_("Recevoir les notifications par e-mail"), required=False)
    notify_sms = forms.BooleanField(label=_("Recevoir les notifications par SMS"), required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        profile = getattr(user, "client_profile", None)
        kwargs.setdefault("initial", {
            "first_name": user.first_name, "last_name": user.last_name, "phone": user.phone or "",
            "language": user.language, "city": profile.city if profile else None,
            "address": profile.address if profile else "", "notify_email": profile.notify_email if profile else True,
            "notify_sms": profile.notify_sms if profile else False,
        })
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.filter(is_active=True)

    def clean_phone(self):
        raw = self.cleaned_data.get("phone", "")
        if not raw:
            return None
        validate_phone(raw)
        phone = normalize_phone(raw)
        if User.objects.filter(phone=phone).exclude(pk=self.user.pk).exists():
            raise ValidationError(_("Ce numéro est déjà utilisé par un autre compte."))
        return phone

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size") and avatar.size > MAX_AVATAR_MB * 1024 * 1024:
            raise ValidationError(_("La photo ne doit pas dépasser %(mb)d Mo."), params={"mb": MAX_AVATAR_MB})
        return avatar

    def save(self):
        from .models import ClientProfile

        data, user = self.cleaned_data, self.user
        user.first_name, user.last_name, user.language = data["first_name"], data["last_name"], data["language"]
        if data["phone"] != user.phone:
            user.phone, user.phone_verified = data["phone"], False
        if data["avatar"]:
            user.avatar = data["avatar"]
        elif data["remove_avatar"]:
            user.avatar = ""
        user.save()
        profile, _created = ClientProfile.objects.get_or_create(user=user)
        profile.city, profile.address = data["city"], data["address"]
        profile.notify_email, profile.notify_sms = data["notify_email"], data["notify_sms"]
        profile.save()
        return user


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class DeleteAccountForm(StyledFormMixin, forms.Form):
    password = forms.CharField(label=_("Votre mot de passe"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError(_("Mot de passe incorrect."))
        return password
