from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import City
from apps.core.forms import StyledFormMixin
from apps.core.site_settings import upload_limit_bytes, upload_limit_mb

from .models import ServiceRequest

MAX_PHOTOS = 5


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Plusieurs images dans un seul champ ; chacune est vérifiée par Pillow et limitée en taille."""

    def __init__(self, *args, max_files=MAX_PHOTOS, **kwargs):
        self.max_files = max_files
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*", "multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        if len(files) > self.max_files:
            raise forms.ValidationError(_("Vous pouvez joindre au maximum %(n)d photos."), params={"n": self.max_files})
        limit = upload_limit_bytes()
        cleaned = []
        for f in files:
            if f.size > limit:
                raise forms.ValidationError(_("« %(name)s » dépasse %(mb)d Mo."), params={"name": f.name, "mb": upload_limit_mb()})
            cleaned.append(single(f, initial))
        return cleaned


class ServiceRequestForm(StyledFormMixin, forms.ModelForm):
    photos = MultipleImageField(
        label=_("Photos (optionnel)"), required=False,
    )

    class Meta:
        model = ServiceRequest
        fields = ["description", "city", "address", "desired_date", "budget"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": _("Décrivez ce dont vous avez besoin : quoi, où, pour quand…")}),
            "desired_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "budget": forms.NumberInput(attrs={"min": 0, "step": 500, "placeholder": _("ex. 25000")}),
            "address": forms.TextInput(attrs={"placeholder": _("Quartier ou adresse")}),
        }
        labels = {"description": _("Votre besoin"), "city": _("Ville"), "address": _("Quartier / adresse"),
                  "desired_date": _("Date souhaitée"), "budget": _("Budget indicatif (FCFA)")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        self.fields["city"].empty_label = None
        self.fields["photos"].help_text = _("Jusqu'à %(n)d images de %(mb)d Mo maximum.") % {"n": MAX_PHOTOS, "mb": upload_limit_mb()}
        self.fields["desired_date"].input_formats = ["%Y-%m-%d"]

    def clean_description(self):
        text = self.cleaned_data["description"].strip()
        if len(text) < 15:
            raise forms.ValidationError(_("Décrivez votre besoin en quelques phrases (15 caractères minimum)."))
        return text

    def clean_desired_date(self):
        value = self.cleaned_data.get("desired_date")
        if value and value < timezone.localdate():
            raise forms.ValidationError(_("La date souhaitée ne peut pas être dans le passé."))
        return value
