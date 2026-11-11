"""Compteurs affichés dans la sidebar du prestataire."""
from apps.requests_app.models import ServiceRequest


def provider_badges(user):
    from apps.core.context_processors import _unread_messages, _unread_notifications

    profile = getattr(user, "provider_profile", None)
    return {
        "new_requests": ServiceRequest.objects.filter(provider=profile, status=ServiceRequest.Status.SENT).count() if profile else 0,
        "messages": _unread_messages(user),
        "notifications": _unread_notifications(user),
    }
