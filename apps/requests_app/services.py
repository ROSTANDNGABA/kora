"""Cycle de vie d'une demande de service. Toute transition passe par ici, ce qui garantit
des changements de statut valides et une notification à l'autre partie (règle de gestion RG-05)."""
from django.db import transaction
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Quote, ServiceRequest

S = ServiceRequest.Status

ALLOWED = {
    S.SENT: {S.VIEWED, S.QUOTED, S.ACCEPTED, S.REFUSED, S.CANCELLED},
    S.VIEWED: {S.QUOTED, S.ACCEPTED, S.REFUSED, S.CANCELLED},
    S.QUOTED: {S.ACCEPTED, S.VIEWED, S.REFUSED, S.CANCELLED},
    S.ACCEPTED: {S.IN_PROGRESS, S.CANCELLED},
    S.IN_PROGRESS: {S.DONE},
    S.DONE: set(),
    S.CANCELLED: set(),
    S.REFUSED: set(),
}
CLIENT_CANCELLABLE = {S.SENT, S.VIEWED, S.QUOTED, S.ACCEPTED}
OPEN_STATUSES = (S.SENT, S.VIEWED, S.QUOTED, S.ACCEPTED, S.IN_PROGRESS)
CLOSED_STATUSES = (S.CANCELLED, S.REFUSED)

_TITLES = {
    S.VIEWED: _("Votre demande a été consultée"),
    S.QUOTED: _("Vous avez reçu un devis"),
    S.ACCEPTED: _("Demande acceptée"),
    S.IN_PROGRESS: _("Votre prestation est en cours"),
    S.DONE: _("Prestation terminée"),
    S.CANCELLED: _("Demande annulée"),
    S.REFUSED: _("Demande refusée"),
}


class InvalidTransition(Exception):
    """Changement de statut impossible depuis l'état actuel."""


def provider_request_url(req):
    """Page de la demande côté prestataire (le tableau de bord complet arrive en phase 4)."""
    try:
        return reverse("dashboard_provider:request_detail", args=[req.pk])
    except NoReverseMatch:
        return reverse("dashboard_provider:home")


def _notify_other_party(req, new_status, actor, title=None):
    if actor.pk == req.client_id:
        recipient, url = req.provider.user, provider_request_url(req)
        who = req.client.public_name
        titles = {
            S.CANCELLED: _("Demande annulée par le client"),
            S.ACCEPTED: _("Devis accepté"),
            S.VIEWED: _("Devis refusé par le client"),
        }
    else:
        recipient, url = req.client, reverse("requests_app:detail", args=[req.pk])
        who = req.provider.business_name
        titles = {}
    title = title or titles.get(new_status) or _TITLES.get(new_status, _("Mise à jour de la demande"))
    body = _("Demande #%(id)s · %(who)s") % {"id": req.pk, "who": who}
    if new_status == S.REFUSED and req.refusal_reason:
        body += f" · {req.refusal_reason}"
    notify(recipient, title, body=body, url=url, type=Notification.Type.REQUEST)


@transaction.atomic
def change_status(req, new_status, actor, *, title=None, reason=""):
    """Applique une transition valide, horodate la fin de prestation et prévient l'autre partie."""
    req = ServiceRequest.objects.select_for_update().select_related("client", "provider__user").get(pk=req.pk)
    if new_status not in ALLOWED[req.status]:
        raise InvalidTransition(f"{req.status} -> {new_status}")
    req.status = new_status
    if new_status == S.DONE:
        req.completed_at = timezone.now()
    if new_status == S.REFUSED and reason:
        req.refusal_reason = reason[:200]
    req.save()
    _notify_other_party(req, new_status, actor, title)
    return req


def create_request(*, client, provider, photos=(), **fields):
    with transaction.atomic():
        req = ServiceRequest.objects.create(client=client, provider=provider, **fields)
        for image in photos:
            req.photos.create(image=image)
    notify(
        provider.user, _("Nouvelle demande de %(name)s") % {"name": client.public_name},
        body=fields.get("description", "")[:140], url=provider_request_url(req), type=Notification.Type.REQUEST,
    )
    return req


def cancel_by_client(req, client):
    if req.client_id != client.pk or req.status not in CLIENT_CANCELLABLE:
        raise InvalidTransition("cancel")
    return change_status(req, S.CANCELLED, client)


@transaction.atomic
def accept_quote(quote, client):
    quote = Quote.objects.select_for_update().select_related("request").get(pk=quote.pk)
    req = quote.request
    if req.client_id != client.pk or req.status != S.QUOTED or quote.status != Quote.Status.PENDING:
        raise InvalidTransition("accept")
    if quote.valid_until and quote.valid_until < timezone.localdate():
        raise InvalidTransition("expired")
    quote.status = Quote.Status.ACCEPTED
    quote.save(update_fields=["status"])
    req.quotes.exclude(pk=quote.pk).filter(status=Quote.Status.PENDING).update(status=Quote.Status.DECLINED)
    return change_status(req, S.ACCEPTED, client)


@transaction.atomic
def decline_quote(quote, client):
    quote = Quote.objects.select_for_update().select_related("request").get(pk=quote.pk)
    req = quote.request
    if req.client_id != client.pk or req.status != S.QUOTED or quote.status != Quote.Status.PENDING:
        raise InvalidTransition("decline")
    quote.status = Quote.Status.DECLINED
    quote.save(update_fields=["status"])
    if not req.quotes.filter(status=Quote.Status.PENDING).exists():
        return change_status(req, S.VIEWED, client)  # le prestataire peut renvoyer un autre devis
    return req


QUOTABLE = {S.SENT, S.VIEWED, S.QUOTED}


@transaction.atomic
def send_quote(req, provider_user, *, amount, delay_days, message="", valid_until=None):
    """Le prestataire chiffre sa réponse. La demande passe à « Devis reçu » ; un second devis est autorisé."""
    req = ServiceRequest.objects.select_for_update().select_related("client", "provider__user").get(pk=req.pk)
    if req.status not in QUOTABLE or req.provider.user_id != provider_user.pk:
        raise InvalidTransition("quote")
    quote = Quote.objects.create(request=req, amount=amount, delay_days=delay_days, message=message, valid_until=valid_until)
    if req.status == S.QUOTED:
        notify(
            req.client, _("Nouveau devis reçu"), body=_("Demande #%(id)s · %(who)s") % {"id": req.pk, "who": req.provider.business_name},
            url=reverse("requests_app:detail", args=[req.pk]), type=Notification.Type.REQUEST,
        )
    else:
        change_status(req, S.QUOTED, provider_user)
    return quote
