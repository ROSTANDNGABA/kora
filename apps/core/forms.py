"""Outils de formulaires partagés."""
from django import forms

INPUT_CLASS = "input"
CHECK_CLASS = "h-4 w-4 rounded accent-kora-orange"


class StyledFormMixin:
    """Applique les classes du design system aux widgets d'un formulaire."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                css = CHECK_CLASS
            elif isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect, forms.FileInput)):
                continue
            else:
                css = INPUT_CLASS
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()
