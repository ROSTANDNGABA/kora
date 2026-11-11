from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from .models import Notification


class NotificationListView(LoginRequiredMixin, TemplateView):
    template_name = "notifications/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        only_unread = self.request.GET.get("filtre") == "non-lues"
        qs = Notification.objects.filter(user=self.request.user)
        if only_unread:
            qs = qs.filter(is_read=False)
        ctx.update(page_obj=Paginator(qs, 20).get_page(self.request.GET.get("page")), only_unread=only_unread, nav_section="notifications")
        return ctx


def _safe_local(url):
    return url if url.startswith("/") and not url.startswith("//") else ""


class NotificationOpenView(LoginRequiredMixin, View):
    """Marque la notification comme lue puis ouvre sa cible. POST uniquement : un GET ne modifie rien."""

    http_method_names = ["post"]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return redirect(_safe_local(notification.url) or reverse("notifications:list"))


class MarkAllReadView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, _("Toutes les notifications sont marquées comme lues.") if count else _("Aucune notification à marquer."))
        return redirect("notifications:list")
