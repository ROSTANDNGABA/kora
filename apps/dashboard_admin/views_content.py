"""Contenu (bannières, pages, FAQ, mise en avant) et communication (annonces, notifications ciblées)."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView

from apps.accounts.models import User
from apps.cms.models import FAQ, Banner, StaticPage
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.providers.models import ProviderProfile

from . import audit
from .forms import AnnouncementForm, BannerForm, FAQForm, StaticPageForm, TargetedNotificationForm
from .models import Announcement
from .permissions import AdminModuleMixin
from .views_base import AdminPage, CrudDeleteView, CrudFormView, ObjectAction, paginate, safe_next


class ContentView(AdminPage):
    module = "content"
    template_name = "dashboard_admin/content.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            banners=Banner.objects.all(), pages=StaticPage.objects.all(), faqs=FAQ.objects.all(),
            featured=ProviderProfile.objects.filter(is_featured=True).select_related("category", "city"),
        )
        return ctx


class BannerFormView(CrudFormView):
    delete_url_name = "dashboard_admin:banner_delete"
    module, model, form_class, audit_name = "content", Banner, BannerForm, "banner"
    list_url_name = "dashboard_admin:content"
    heading_new, heading_edit = "Nouvelle bannière", "Modifier la bannière"
    multipart = True


class BannerDeleteView(CrudDeleteView):
    module, model, audit_name, list_url_name = "content", Banner, "banner", "dashboard_admin:content"


class PageFormView(CrudFormView):
    delete_url_name = "dashboard_admin:page_delete"
    module, model, form_class, audit_name = "content", StaticPage, StaticPageForm, "page"
    list_url_name = "dashboard_admin:content"
    heading_new, heading_edit = "Nouvelle page", "Modifier la page"


class PageDeleteView(CrudDeleteView):
    module, model, audit_name, list_url_name = "content", StaticPage, "page", "dashboard_admin:content"


class FAQFormView(CrudFormView):
    delete_url_name = "dashboard_admin:faq_delete"
    module, model, form_class, audit_name = "content", FAQ, FAQForm, "faq"
    list_url_name = "dashboard_admin:content"
    heading_new, heading_edit = "Nouvelle question", "Modifier la question"


class FAQDeleteView(CrudDeleteView):
    module, model, audit_name, list_url_name = "content", FAQ, "faq", "dashboard_admin:content"


class ContentToggleView(ObjectAction):
    """Publie ou masque une bannière, une page ou une question."""

    module = "content"
    model = None
    field = "is_active"
    audit_name = ""

    def get_queryset(self):
        return self.model.objects.all()

    def get_redirect(self, request, obj):
        return safe_next(request, reverse("dashboard_admin:content"))

    def perform(self, request, obj, reason):
        setattr(obj, self.field, not getattr(obj, self.field))
        obj.save(update_fields=[self.field])
        on = getattr(obj, self.field)
        audit.log(request, f"{self.audit_name}.{'enable' if on else 'disable'}", obj)
        self.success = "Publié." if on else "Masqué."


class BannerToggleView(ContentToggleView):
    model, audit_name = Banner, "banner"


class PageToggleView(ContentToggleView):
    model, field, audit_name = StaticPage, "is_published", "page"


class FAQToggleView(ContentToggleView):
    model, audit_name = FAQ, "faq"


class UnfeatureView(ObjectAction):
    module = "content"
    success = "Prestataire retiré de la mise en avant."

    def get_queryset(self):
        return ProviderProfile.objects.filter(is_featured=True)

    def get_redirect(self, request, obj):
        return safe_next(request, reverse("dashboard_admin:content"))

    def perform(self, request, p, reason):
        p.is_featured = False
        p.save(update_fields=["is_featured", "updated_at"])
        audit.log(request, "provider.unfeature", p)


# --- Communication -----------------------------------------------------------
class CommunicationView(AdminModuleMixin, FormView):
    module = "communication"
    template_name = "dashboard_admin/communication.html"
    form_class = AnnouncementForm
    success_url = None

    def get_success_url(self):
        return reverse("dashboard_admin:communication")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            targeted_form=kwargs.get("targeted_form") or TargetedNotificationForm(),
            history=paginate(self.request, Announcement.objects.select_related("created_by"), 10),
            counts={
                "ALL": User.objects.filter(is_active=True).exclude(role=User.Role.ADMIN).count(),
                "CLIENTS": User.objects.filter(is_active=True, role=User.Role.CLIENT).count(),
                "PROVIDERS": User.objects.filter(is_active=True, role=User.Role.PROVIDER).count(),
            },
        )
        return ctx

    def form_valid(self, form):
        ann = form.save(commit=False)
        roles = {"ALL": [User.Role.CLIENT, User.Role.PROVIDER], "CLIENTS": [User.Role.CLIENT], "PROVIDERS": [User.Role.PROVIDER]}[ann.audience]
        users = User.objects.filter(is_active=True, role__in=roles)
        ann.created_by = self.request.user
        with transaction.atomic():
            ann.recipients_count = users.count()
            ann.save()
            Notification.objects.bulk_create(
                [Notification(user=u, type=Notification.Type.ANNOUNCEMENT, title=ann.title, body=ann.body, url=ann.url) for u in users.iterator()],
                batch_size=500,
            )
        audit.log(self.request, "announcement.send", ann, {"audience": ann.audience, "destinataires": ann.recipients_count})
        messages.success(self.request, f"Annonce envoyée à {ann.recipients_count} utilisateur(s).")
        return redirect(self.get_success_url())


class TargetedNotificationView(AdminModuleMixin, FormView):
    module = "communication"
    http_method_names = ["post"]
    form_class = TargetedNotificationForm

    def form_valid(self, form):
        notify(form.user, form.cleaned_data["title"], body=form.cleaned_data["body"], type=Notification.Type.ANNOUNCEMENT)
        audit.log(self.request, "notification.send", form.user, {"titre": form.cleaned_data["title"]})
        messages.success(self.request, "Notification envoyée.")
        return redirect("dashboard_admin:communication")

    def form_invalid(self, form):
        for errors in form.errors.values():
            messages.error(self.request, errors[0])
        return redirect("dashboard_admin:communication")
