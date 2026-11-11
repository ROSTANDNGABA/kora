from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.site_settings import upload_limit_bytes, upload_limit_mb


class MessageForm(forms.Form):
    body = forms.CharField(
        label=_("Message"), required=False, max_length=2000, strip=True,
        widget=forms.Textarea(attrs={"rows": 2, "class": "input resize-none", "placeholder": _("Écrivez votre message…"), "maxlength": 2000}),
    )
    attachment = forms.ImageField(label=_("Image"), required=False, widget=forms.FileInput(attrs={"accept": "image/*", "class": "sr-only"}))

    def clean_attachment(self):
        image = self.cleaned_data.get("attachment")
        if image and image.size > upload_limit_bytes():
            raise forms.ValidationError(_("L'image dépasse %(mb)d Mo."), params={"mb": upload_limit_mb()})
        return image

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("body") and not cleaned.get("attachment") and not self.errors:
            raise forms.ValidationError(_("Écrivez un message ou joignez une image."))
        return cleaned
