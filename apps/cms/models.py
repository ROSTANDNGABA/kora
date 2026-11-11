from django.db import models
from django.utils.translation import gettext_lazy as _


class Banner(models.Model):
    title = models.CharField(_("titre"), max_length=120)
    subtitle = models.CharField(_("sous-titre"), max_length=200, blank=True)
    image = models.ImageField(_("image"), upload_to="banners/", blank=True)
    link_url = models.CharField(_("lien"), max_length=300, blank=True)
    link_label = models.CharField(_("texte du bouton"), max_length=60, blank=True)
    order = models.PositiveIntegerField(_("ordre"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("bannière")
        verbose_name_plural = _("bannières")
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class StaticPage(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(_("titre"), max_length=160)
    body = models.TextField(_("contenu"))
    is_published = models.BooleanField(_("publiée"), default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("page statique")
        verbose_name_plural = _("pages statiques")
        ordering = ["title"]

    def __str__(self):
        return self.title


class FAQ(models.Model):
    question = models.CharField(_("question"), max_length=220)
    answer = models.TextField(_("réponse"))
    order = models.PositiveIntegerField(_("ordre"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("question fréquente")
        verbose_name_plural = _("FAQ")
        ordering = ["order", "id"]

    def __str__(self):
        return self.question
