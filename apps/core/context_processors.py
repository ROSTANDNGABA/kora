from django.conf import settings
from django.contrib.messages import get_messages

from apps.catalog.models import Category
from apps.core import site_settings
from apps.cms.models import StaticPage


def _unread_notifications(user):
    from apps.notifications.models import Notification

    return Notification.objects.filter(user=user, is_read=False).count()


def _unread_messages(user):
    from django.db.models import Q

    from apps.messaging.models import Message

    return (
        Message.objects.filter(read_at__isnull=True)
        .filter(Q(conversation__client=user) | Q(conversation__provider__user=user))
        .exclude(sender=user)
        .count()
    )


LAYOUTS = {
    "PROVIDER": "dashboard_provider/layout.html",
    "ADMIN": "dashboard_admin/layout.html",
}


def site(request):
    """Variables disponibles dans tous les templates. Les listes du pied de page sont chargées à la demande."""
    user = getattr(request, "user", None)
    signed_in = bool(user and user.is_authenticated)
    return {
        # Gabarit parent des pages partagées (messagerie, notifications, mot de passe) : selon le rôle.
        "layout": LAYOUTS.get(getattr(user, "role", ""), "client/layout.html") if signed_in else "client/layout.html",
        "unread_notifications": (lambda: _unread_notifications(user)) if signed_in else (lambda: 0),
        "unread_messages": (lambda: _unread_messages(user)) if signed_in else (lambda: 0),
        "SITE_NAME": "Kora",
        "SITE_SLOGAN": site_settings.get("site_slogan") or "Le savoir-faire camerounais, à portée de main.",
        "SUPPORT_WHATSAPP": site_settings.get("support_whatsapp"),
        "SOCIAL_LINKS": {k: v for k, v in settings.SOCIAL_LINKS.items() if v},
        "DEBUG": settings.DEBUG,
        "toast_messages": [{"type": m.level_tag, "text": str(m)} for m in get_messages(request)],
        "footer_pages": lambda: list(StaticPage.objects.filter(is_published=True)),
        "footer_categories": lambda: list(Category.objects.filter(is_active=True)[:6]),
    }
