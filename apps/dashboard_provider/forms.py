from datetime import time

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User, normalize_phone, validate_phone
from apps.catalog.models import Category, CategoryField, Neighborhood
from apps.core.forms import StyledFormMixin
from apps.core.images import compress_image
from apps.core.site_settings import upload_limit_bytes, upload_limit_mb
from apps.providers.models import Availability, ProviderFieldValue, ProviderProfile, Service, Verification
from apps.requests_app.forms import MultipleImageField
from apps.requests_app.models import Quote


def check_image_size(image):
    if image and hasattr(image, "size") and image.size > upload_limit_bytes():
        raise ValidationError(_("L'image dépasse %(mb)d Mo."), params={"mb": upload_limit_mb()})
    return image


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """Profil public : champs fixes + champs spécifiques au métier générés depuis la catégorie."""

    new_category = forms.ModelChoiceField(
        label=_("Demander un changement de métier principal"), queryset=Category.objects.none(), required=False,
        empty_label=_("Aucun changement"), help_text=_("Soumis à la validation de l'équipe Kora. Votre métier actuel reste affiché en attendant."),
    )
    cancel_category_change = forms.BooleanField(label=_("Annuler ma demande de changement de métier"), required=False)

    class Meta:
        model = ProviderProfile
        fields = ["business_name", "activity_type", "description", "logo", "city", "whatsapp", "subcategories"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5, "maxlength": 1500}),
            "subcategories": forms.CheckboxSelectMultiple,
            "logo": forms.FileInput(attrs={"accept": "image/*", "class": "block w-full text-sm"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = self.instance
        self.fields["subcategories"].queryset = profile.category.subcategories.filter(is_active=True)
        self.fields["subcategories"].required = False
        self.fields["city"].queryset = self.fields["city"].queryset.filter(is_active=True) | self.fields["city"].queryset.filter(pk=profile.city_id)
        self.fields["new_category"].queryset = Category.objects.filter(is_active=True).exclude(pk=profile.category_id)
        if not profile.pending_category_id:
            del self.fields["cancel_category_change"]
        self.dynamic = list(profile.category.fields.filter(is_active=True))
        existing = {v.field_id: v.value for v in profile.field_values.all()}
        for f in self.dynamic:
            self.fields[f"extra_{f.pk}"] = self._build_field(f, existing.get(f.pk))

    def _build_field(self, f, value):
        common = {"label": f.label, "required": f.is_required, "initial": value}
        if f.field_type == CategoryField.FieldType.BOOLEAN:
            return forms.BooleanField(label=f.label, required=False, initial=str(value).lower() in ("true", "1", "oui"),
                                      widget=forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded accent-kora-orange"}))
        if f.field_type == CategoryField.FieldType.NUMBER:
            return forms.DecimalField(**{**common, "initial": value or None}, widget=forms.NumberInput(attrs={"class": "input", "step": "any"}), max_digits=12, decimal_places=2)
        if f.field_type == CategoryField.FieldType.CHOICE:
            return forms.ChoiceField(label=f.label, required=f.is_required, initial=value,
                                     choices=[("", "—")] + [(c, c) for c in f.choice_list], widget=forms.Select(attrs={"class": "input"}))
        return forms.CharField(**common, max_length=300, widget=forms.TextInput(attrs={"class": "input"}))

    def clean_logo(self):
        return check_image_size(self.cleaned_data.get("logo"))

    def clean_whatsapp(self):
        raw = self.cleaned_data["whatsapp"]
        validate_phone(raw)
        return normalize_phone(raw).lstrip("+")

    def save(self, commit=True):
        profile = super().save(commit=False)
        logo = self.cleaned_data.get("logo")
        if logo and "logo" in self.changed_data and hasattr(logo, "read"):
            profile.logo = compress_image(logo, max_side=800)
        new_category = self.cleaned_data.get("new_category")
        if new_category:
            profile.pending_category = new_category
        elif self.cleaned_data.get("cancel_category_change"):
            profile.pending_category = None
        profile.save()
        self.save_m2m()
        for f in self.dynamic:
            raw = self.cleaned_data.get(f"extra_{f.pk}")
            value = ("true" if raw else "false") if f.field_type == CategoryField.FieldType.BOOLEAN else ("" if raw is None else str(raw))
            if value in ("", "false"):
                ProviderFieldValue.objects.filter(provider=profile, field=f).delete()
            else:
                ProviderFieldValue.objects.update_or_create(provider=profile, field=f, defaults={"value": value})
        return profile


class PortfolioUploadForm(forms.Form):
    images = MultipleImageField(label=_("Ajouter des photos"), required=True, max_files=10)

    def __init__(self, *args, remaining=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.remaining = remaining
        self.fields["images"].help_text = _("Plusieurs photos possibles (%(mb)d Mo maximum chacune). Il vous reste %(n)d emplacement(s).") % {"mb": upload_limit_mb(), "n": remaining}

    def clean_images(self):
        images = self.cleaned_data["images"]
        if len(images) > self.remaining:
            raise ValidationError(_("Votre portfolio est limité : il reste %(n)d emplacement(s)."), params={"n": self.remaining})
        return images


class CaptionForm(StyledFormMixin, forms.Form):
    caption = forms.CharField(max_length=160, required=False)


class ServiceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ["title", "description", "price_type", "amount", "duration_minutes", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3, "maxlength": 400}), "amount": forms.NumberInput(attrs={"min": 0, "step": 500})}

    def clean(self):
        cleaned = super().clean()
        kind, amount = cleaned.get("price_type"), cleaned.get("amount")
        if kind in (Service.PriceType.FIXED, Service.PriceType.FROM) and not amount:
            self.add_error("amount", _("Indiquez le montant en FCFA, ou choisissez « Sur devis »."))
        if kind == Service.PriceType.QUOTE:
            cleaned["amount"] = None
        return cleaned


DAYS = Availability.Weekday.choices


class AvailabilityForm(StyledFormMixin, forms.Form):
    """Horaires par jour, zone desservie (quartiers), déplacement à domicile et mode congés."""

    is_unavailable = forms.BooleanField(label=_("Mode congés : je suis indisponible pour le moment"), required=False)
    home_service = forms.BooleanField(label=_("Je me déplace chez le client"), required=False)
    neighborhoods = forms.ModelMultipleChoiceField(label=_("Quartiers desservis"), queryset=Neighborhood.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        saved = {a.weekday: a for a in profile.availabilities.all()}
        initial = {"is_unavailable": profile.is_unavailable, "home_service": profile.home_service, "neighborhoods": profile.neighborhoods.all()}
        for number, _label in DAYS:
            a = saved.get(number)
            initial[f"closed_{number}"] = bool(a and a.is_closed) if a else number == 6
            initial[f"open_{number}"] = a.opens_at if a and a.opens_at else time(8, 0)
            initial[f"close_{number}"] = a.closes_at if a and a.closes_at else time(18, 0)
        kwargs["initial"] = {**initial, **(kwargs.get("initial") or {})}
        super().__init__(*args, **kwargs)
        self.fields["neighborhoods"].queryset = Neighborhood.objects.filter(city=profile.city, is_active=True)
        for number, label in DAYS:
            self.fields[f"closed_{number}"] = forms.BooleanField(label=_("Fermé"), required=False, widget=forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded accent-kora-orange"}))
            self.fields[f"open_{number}"] = forms.TimeField(label=_("Ouverture"), required=False, widget=forms.TimeInput(attrs={"type": "time", "class": "input py-1.5"}, format="%H:%M"))
            self.fields[f"close_{number}"] = forms.TimeField(label=_("Fermeture"), required=False, widget=forms.TimeInput(attrs={"type": "time", "class": "input py-1.5"}, format="%H:%M"))

    @property
    def day_rows(self):
        return [
            {"label": label, "closed": self[f"closed_{n}"], "open": self[f"open_{n}"], "close": self[f"close_{n}"]}
            for n, label in DAYS
        ]

    def clean(self):
        cleaned = super().clean()
        for number, label in DAYS:
            if cleaned.get(f"closed_{number}"):
                continue
            opens, closes = cleaned.get(f"open_{number}"), cleaned.get(f"close_{number}")
            if not opens or not closes:
                self.add_error(f"open_{number}", _("%(day)s : indiquez l'ouverture et la fermeture, ou cochez « Fermé ».") % {"day": label})
            elif closes <= opens:
                self.add_error(f"close_{number}", _("%(day)s : la fermeture doit être après l'ouverture.") % {"day": label})
        return cleaned

    def save(self):
        p, data = self.profile, self.cleaned_data
        p.is_unavailable, p.home_service = data["is_unavailable"], data["home_service"]
        p.save(update_fields=["is_unavailable", "home_service", "updated_at"])
        p.neighborhoods.set(data["neighborhoods"])
        for number, _label in DAYS:
            closed = data[f"closed_{number}"]
            Availability.objects.update_or_create(
                provider=p, weekday=number,
                defaults={"is_closed": closed, "opens_at": None if closed else data[f"open_{number}"], "closes_at": None if closed else data[f"close_{number}"]},
            )


class QuoteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Quote
        fields = ["amount", "delay_days", "valid_until", "message"]
        widgets = {
            "amount": forms.NumberInput(attrs={"min": 1, "step": 500}), "delay_days": forms.NumberInput(attrs={"min": 1, "max": 365}),
            "valid_until": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), "message": forms.Textarea(attrs={"rows": 3, "maxlength": 800}),
        }
        labels = {"amount": _("Montant du devis (FCFA)"), "delay_days": _("Délai de réalisation (jours)"), "valid_until": _("Valable jusqu'au"), "message": _("Message au client")}

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount < 1:
            raise ValidationError(_("Le montant doit être supérieur à zéro."))
        return amount

    def clean_delay_days(self):
        days = self.cleaned_data["delay_days"]
        if not 1 <= days <= 365:
            raise ValidationError(_("Indiquez un délai entre 1 et 365 jours."))
        return days

    def clean_valid_until(self):
        value = self.cleaned_data.get("valid_until")
        if value and value < timezone.localdate():
            raise ValidationError(_("La date de validité ne peut pas être dans le passé."))
        return value


class RefuseForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(label=_("Motif (visible par le client)"), max_length=200, required=False, widget=forms.TextInput(attrs={"placeholder": _("Ex. : planning complet jusqu'en janvier")}))


class ReplyForm(StyledFormMixin, forms.Form):
    reply = forms.CharField(label=_("Votre réponse publique"), max_length=1000, widget=forms.Textarea(attrs={"rows": 3, "maxlength": 1000}))

    def clean_reply(self):
        text = self.cleaned_data["reply"].strip()
        if not text:
            raise ValidationError(_("Écrivez votre réponse."))
        return text


MAGIC = {b"%PDF": "pdf", b"\x89PNG": "png", b"\xff\xd8\xff": "jpg"}


def validate_document(file):
    """Pièce justificative : PDF, JPG ou PNG, contrôlé par le contenu réel (pas seulement l'extension)."""
    if file.size > upload_limit_bytes():
        raise ValidationError(_("Le fichier dépasse %(mb)d Mo."), params={"mb": upload_limit_mb()})
    file.seek(0)
    head = file.read(4)
    file.seek(0)
    kind = next((k for magic, k in MAGIC.items() if head.startswith(magic)), None)
    ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    if kind is None or (kind == "jpg" and ext not in ("jpg", "jpeg")) or (kind != "jpg" and ext != kind):
        raise ValidationError(_("Format non accepté : envoyez un PDF, un JPG ou un PNG."))
    return file


class VerificationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Verification
        fields = ["id_document", "activity_proof"]
        widgets = {
            "id_document": forms.FileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png", "class": "block w-full text-sm"}),
            "activity_proof": forms.FileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png", "class": "block w-full text-sm"}),
        }
        labels = {"id_document": _("Pièce d'identité (CNI, passeport)"), "activity_proof": _("Preuve d'activité (facultatif)")}

    def clean_id_document(self):
        return validate_document(self.cleaned_data["id_document"])

    def clean_activity_proof(self):
        doc = self.cleaned_data.get("activity_proof")
        return validate_document(doc) if doc else doc


class ProviderAccountForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(label=_("Prénom"), max_length=150)
    last_name = forms.CharField(label=_("Nom"), max_length=150)
    phone = forms.CharField(label=_("Téléphone de connexion"), required=False, max_length=20)
    avatar = forms.ImageField(label=_("Photo de profil"), required=False, widget=forms.FileInput(attrs={"accept": "image/*", "class": "block w-full text-sm"}))
    language = forms.ChoiceField(label=_("Langue"), choices=[("fr", "Français"), ("en", "English")])

    def __init__(self, *args, user, **kwargs):
        self.user = user
        kwargs.setdefault("initial", {"first_name": user.first_name, "last_name": user.last_name, "phone": user.phone or "", "language": user.language})
        super().__init__(*args, **kwargs)

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
        return check_image_size(self.cleaned_data.get("avatar"))

    def save(self):
        user, data = self.user, self.cleaned_data
        user.first_name, user.last_name, user.language = data["first_name"], data["last_name"], data["language"]
        if data["phone"] != user.phone:
            user.phone, user.phone_verified = data["phone"], False
        if data["avatar"]:
            user.avatar = compress_image(data["avatar"], max_side=600)
        user.save()
        return user
