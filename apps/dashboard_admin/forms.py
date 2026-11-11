from django import forms
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.catalog.models import Category, CategoryField, City, Neighborhood, Subcategory
from apps.cms.models import FAQ, Banner, StaticPage
from apps.core.forms import StyledFormMixin
from apps.core.images import compress_image
from apps.core.models import SiteSettings
from apps.providers.models import ProviderProfile

from .models import Announcement


class ReasonForm(StyledFormMixin, forms.Form):
    """Motif saisi dans une modale de confirmation (refus, suspension, masquage...)."""

    reason = forms.CharField(label=_("Motif"), max_length=400, required=False, widget=forms.Textarea(attrs={"rows": 3}))


class RequiredReasonForm(ReasonForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].required = True

    def clean_reason(self):
        text = self.cleaned_data["reason"].strip()
        if len(text) < 5:
            raise ValidationError(_("Expliquez brièvement le motif (5 caractères minimum)."))
        return text


class ProviderEditForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProviderProfile
        fields = ["business_name", "activity_type", "category", "city", "whatsapp", "description", "is_featured"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class CategoryForm(StyledFormMixin, forms.ModelForm):
    slug = forms.CharField(label=_("Adresse (slug)"), required=False, max_length=90, help_text=_("Laissez vide pour la générer à partir du nom."))

    class Meta:
        model = Category
        fields = ["name", "slug", "icon", "color", "banner", "description", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "color": forms.TextInput(attrs={"type": "color"}), "banner": forms.FileInput(attrs={"accept": "image/*"})}

    def clean_slug(self):
        return slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name", ""))

    def clean_color(self):
        color = self.cleaned_data["color"]
        if len(color) != 7 or not color.startswith("#") or any(c not in "0123456789abcdefABCDEF" for c in color[1:]):
            raise ValidationError(_("Couleur invalide (format #RRGGBB)."))
        return color

    def clean_banner(self):
        file = self.cleaned_data.get("banner")
        if file and hasattr(file, "content_type"):
            return compress_image(file)
        return file


class SubcategoryForm(StyledFormMixin, forms.ModelForm):
    slug = forms.CharField(label=_("Adresse (slug)"), required=False, max_length=90)

    class Meta:
        model = Subcategory
        fields = ["category", "name", "slug", "order", "is_active"]

    def clean(self):
        cleaned = super().clean()
        cleaned["slug"] = slugify(cleaned.get("slug") or cleaned.get("name", ""))
        cat, slug = cleaned.get("category"), cleaned["slug"]
        qs = Subcategory.objects.filter(category=cat, slug=slug).exclude(pk=self.instance.pk)
        if cat and slug and qs.exists():
            self.add_error("name", _("Cette sous-catégorie existe déjà dans cette catégorie."))
        return cleaned


class CategoryFieldForm(StyledFormMixin, forms.ModelForm):
    key = forms.CharField(label=_("Clé technique"), required=False, max_length=60, help_text=_("Laissez vide pour la générer à partir du libellé."))

    class Meta:
        model = CategoryField
        fields = ["category", "label", "key", "field_type", "choices", "is_required", "order", "is_active"]
        widgets = {"choices": forms.Textarea(attrs={"rows": 4, "placeholder": "Un choix par ligne"})}

    def clean(self):
        cleaned = super().clean()
        cleaned["key"] = slugify(cleaned.get("key") or cleaned.get("label", "")).replace("-", "_")
        if cleaned.get("field_type") == CategoryField.FieldType.CHOICE and len([c for c in cleaned.get("choices", "").splitlines() if c.strip()]) < 2:
            self.add_error("choices", _("Un champ à choix doit proposer au moins deux options."))
        cat = cleaned.get("category")
        if cat and cleaned["key"] and CategoryField.objects.filter(category=cat, key=cleaned["key"]).exclude(pk=self.instance.pk).exists():
            self.add_error("label", _("Un champ avec cette clé existe déjà pour cette catégorie."))
        return cleaned


class CityForm(StyledFormMixin, forms.ModelForm):
    slug = forms.CharField(label=_("Adresse (slug)"), required=False, max_length=90)

    class Meta:
        model = City
        fields = ["name", "slug", "region", "order", "is_active"]

    def clean_slug(self):
        return slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name", ""))


class NeighborhoodForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Neighborhood
        fields = ["city", "name", "is_active"]


class BannerForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Banner
        fields = ["title", "subtitle", "image", "link_url", "link_label", "order", "is_active"]
        widgets = {"image": forms.FileInput(attrs={"accept": "image/*"})}

    def clean_link_url(self):
        url = self.cleaned_data["link_url"].strip()
        if url and not (url.startswith("/") and not url.startswith("//")) and not url.startswith("https://"):
            raise ValidationError(_("Le lien doit commencer par / (page du site) ou https://."))
        return url

    def clean_image(self):
        file = self.cleaned_data.get("image")
        if file and hasattr(file, "content_type"):
            return compress_image(file)
        return file


class StaticPageForm(StyledFormMixin, forms.ModelForm):
    slug = forms.CharField(label=_("Adresse de la page"), max_length=80, help_text=_("Ex. : mentions-legales"))

    class Meta:
        model = StaticPage
        fields = ["title", "slug", "body", "is_published"]
        widgets = {"body": forms.Textarea(attrs={"rows": 12})}

    def clean_slug(self):
        slug = slugify(self.cleaned_data["slug"])
        if not slug:
            raise ValidationError(_("Adresse invalide."))
        if StaticPage.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_("Une page utilise déjà cette adresse."))
        return slug


class FAQForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ["question", "answer", "order", "is_active"]
        widgets = {"answer": forms.Textarea(attrs={"rows": 4})}


class AnnouncementForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["audience", "title", "body", "url"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "maxlength": 1000})}

    def clean_url(self):
        url = self.cleaned_data["url"].strip()
        if url and not (url.startswith("/") and not url.startswith("//")):
            raise ValidationError(_("Le lien doit être une page du site (commence par /)."))
        return url


class TargetedNotificationForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label=_("E-mail du destinataire"))
    title = forms.CharField(label=_("Titre"), max_length=140)
    body = forms.CharField(label=_("Message"), max_length=600, widget=forms.Textarea(attrs={"rows": 3}))

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            raise ValidationError(_("Aucun compte actif ne correspond à cette adresse."))
        self.user = user
        return email


class TeamMemberForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label=_("E-mail"))
    first_name = forms.CharField(label=_("Prénom"), max_length=150)
    last_name = forms.CharField(label=_("Nom"), max_length=150)
    password = forms.CharField(label=_("Mot de passe provisoire"), widget=forms.PasswordInput(render_value=False), min_length=10, required=False, help_text=_("10 caractères minimum. Laissez vide en modification pour ne pas le changer."))
    groups = forms.ModelMultipleChoiceField(label=_("Rôles"), queryset=Group.objects.all(), widget=forms.CheckboxSelectMultiple, required=False)
    is_active = forms.BooleanField(label=_("Compte actif"), required=False, initial=True)

    def __init__(self, *args, member=None, **kwargs):
        self.member = member
        if member:
            kwargs["initial"] = {"email": member.email, "first_name": member.first_name, "last_name": member.last_name, "groups": member.groups.all(), "is_active": member.is_active, **(kwargs.get("initial") or {})}
        super().__init__(*args, **kwargs)
        if member:
            self.fields["email"].disabled = True

    def clean_email(self):
        if self.member:
            return self.member.email
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("Un compte existe déjà avec cette adresse."))
        return email

    def clean(self):
        cleaned = super().clean()
        if not self.member and not cleaned.get("password"):
            self.add_error("password", _("Choisissez un mot de passe provisoire."))
        if cleaned.get("password"):
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(cleaned["password"])
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned


class SiteSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ["site_slogan", "support_whatsapp", "contact_email", "upload_max_mb", "portfolio_max_items"]

    def clean_support_whatsapp(self):
        raw = self.cleaned_data["support_whatsapp"].strip().lstrip("+").replace(" ", "")
        if raw and not raw.isdigit():
            raise ValidationError(_("Chiffres uniquement, avec l'indicatif (ex. 237600000000)."))
        return raw
