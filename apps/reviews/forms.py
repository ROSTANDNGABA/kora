from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledFormMixin

from .models import Report, Review

REPORT_REASONS = [
    ("spam", _("Spam ou publicité")),
    ("fake", _("Faux profil ou faux avis")),
    ("abuse", _("Propos injurieux ou inappropriés")),
    ("scam", _("Tentative d'arnaque")),
    ("other", _("Autre motif")),
]


class ReviewForm(StyledFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        label=_("Votre note"), coerce=int, choices=[(i, str(i)) for i in range(5, 0, -1)], widget=forms.RadioSelect,
        error_messages={"required": _("Choisissez une note de 1 à 5 étoiles.")},
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 5, "maxlength": 1500, "placeholder": _("Racontez comment s'est passée la prestation (facultatif).")})}
        labels = {"comment": _("Votre commentaire")}

    def clean_comment(self):
        return self.cleaned_data["comment"].strip()


class ReportForm(StyledFormMixin, forms.ModelForm):
    reason = forms.ChoiceField(label=_("Motif"), choices=REPORT_REASONS)

    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 4, "maxlength": 1000, "placeholder": _("Précisez si besoin.")})}
        labels = {"details": _("Détails (facultatif)")}

    def clean_reason(self):
        return dict(REPORT_REASONS)[self.cleaned_data["reason"]]
