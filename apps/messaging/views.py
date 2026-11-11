from django.contrib import messages
from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.accounts.models import User
from apps.core import ratelimit
from apps.core.mixins import RoleRequiredMixin
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.providers.models import ProviderProfile
from apps.requests_app.models import ServiceRequest

from .forms import MessageForm
from .models import Conversation, Message

MESSAGE_LIMIT_PER_MINUTE = 20
THREAD_SIZE = 100


class ParticipantMixin(RoleRequiredMixin):
    """Clients et prestataires uniquement ; chacun ne voit que ses propres conversations."""

    allowed_roles = (User.Role.CLIENT, User.Role.PROVIDER)

    def conversations(self):
        user = self.request.user
        field = {"client": user} if user.is_client else {"provider__user": user}
        return Conversation.objects.filter(**field).select_related("client", "provider", "provider__user")


def counterpart_name(conversation, user):
    return conversation.provider.business_name if user.is_client else conversation.client.public_name


class InboxView(ParticipantMixin, TemplateView):
    template_name = "messaging/inbox.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        last = Message.objects.filter(conversation=OuterRef("pk")).order_by("-created_at")
        convs = list(
            self.conversations().annotate(
                unread=Count("messages", filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user)),
                last_body=Subquery(last.values("body")[:1]),
                last_has_image=Subquery(last.exclude(attachment="").values("pk")[:1]),
                last_sender=Subquery(last.values("sender_id")[:1]),
            )
        )
        for c in convs:
            c.other_name = counterpart_name(c, user)
            c.preview = c.last_body or (_("Image") if c.last_has_image else "")
            c.mine = c.last_sender == user.pk
        ctx.update(conversations=convs, nav_section="messages")
        return ctx


class _ThreadBase(ParticipantMixin):
    def get_conversation(self):
        return get_object_or_404(self.conversations(), pk=self.kwargs["pk"])

    def mark_read(self, conversation):
        conversation.messages.filter(read_at__isnull=True).exclude(sender=self.request.user).update(read_at=timezone.now())

    def can_send(self, conversation):
        """Un prestataire suspendu ne reçoit plus de messages ; lui-même ne peut plus écrire."""
        return conversation.provider.status == ProviderProfile.Status.ACTIVE and conversation.provider.user.is_active


class ThreadView(_ThreadBase, FormView):
    template_name = "messaging/thread.html"
    form_class = MessageForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        conversation = self.conversation
        self.mark_read(conversation)
        ctx.update(
            conversation=conversation, other_name=counterpart_name(conversation, self.request.user),
            thread=list(conversation.messages.select_related("sender").order_by("-created_at")[:THREAD_SIZE])[::-1],
            can_send=self.can_send(conversation), nav_section="messages",
            can_report=self.request.user.is_client,
        )
        return ctx

    def get(self, request, *args, **kwargs):
        self.conversation = self.get_conversation()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.conversation = self.get_conversation()
        if not self.can_send(self.conversation):
            messages.error(request, _("Cette conversation n'accepte plus de nouveaux messages."))
            return redirect("messaging:thread", pk=self.conversation.pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user, conversation = self.request.user, self.conversation
        if ratelimit.is_limited("message", str(user.pk), MESSAGE_LIMIT_PER_MINUTE):
            messages.error(self.request, _("Vous envoyez trop de messages. Patientez une minute."))
            return redirect("messaging:thread", pk=conversation.pk)
        ratelimit.hit("message", str(user.pk), 60)
        msg = Message.objects.create(
            conversation=conversation, sender=user, body=form.cleaned_data["body"], attachment=form.cleaned_data["attachment"] or "",
        )
        conversation.updated_at = msg.created_at
        conversation.save(update_fields=["updated_at"])
        recipient = conversation.provider.user if user.is_client else conversation.client
        url = reverse("messaging:thread", args=[conversation.pk])
        name = user.public_name if user.is_client else conversation.provider.business_name
        # Une seule notification non lue par conversation, pour ne pas inonder la cloche.
        if not Notification.objects.filter(user=recipient, type=Notification.Type.MESSAGE, url=url, is_read=False).exists():
            notify(recipient, _("Nouveau message de %(name)s") % {"name": name}, body=msg.body[:140] or _("Image"), url=url, type=Notification.Type.MESSAGE)
        return redirect("messaging:thread", pk=conversation.pk)

    def get_success_url(self):  # pragma: no cover - form_valid redirige déjà
        return reverse("messaging:thread", args=[self.conversation.pk])


class ThreadFragmentView(_ThreadBase, TemplateView):
    """Rafraîchissement HTMX du fil (toutes les quelques secondes)."""

    template_name = "messaging/partials/thread_messages.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        conversation = self.get_conversation()
        self.mark_read(conversation)
        ctx["thread"] = list(conversation.messages.select_related("sender").order_by("-created_at")[:THREAD_SIZE])[::-1]
        return ctx


class StartFromProviderView(RoleRequiredMixin, View):
    """Un client ouvre (ou retrouve) la conversation avec un prestataire public."""

    allowed_roles = (User.Role.CLIENT,)
    http_method_names = ["post"]

    def post(self, request, slug):
        provider = get_object_or_404(ProviderProfile.objects.public(), slug=slug)
        conversation, _created = Conversation.objects.get_or_create(client=request.user, provider=provider)
        return redirect("messaging:thread", pk=conversation.pk)


class StartFromRequestView(ParticipantMixin, View):
    """Depuis une demande : le client ou le prestataire concerné ouvre la conversation liée."""

    http_method_names = ["post"]

    def post(self, request, pk):
        user = request.user
        field = {"client": user} if user.is_client else {"provider__user": user}
        req = get_object_or_404(ServiceRequest, pk=pk, **field)
        conversation, created = Conversation.objects.get_or_create(
            client=req.client, provider=req.provider, defaults={"request": req}
        )
        if not created and conversation.request_id is None:
            conversation.request = req
            conversation.save(update_fields=["request"])
        return redirect("messaging:thread", pk=conversation.pk)
