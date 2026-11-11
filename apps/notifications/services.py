from .models import Notification


def notify(user, title, *, body="", url="", type=Notification.Type.ACCOUNT):
    """Crée une notification interne. L'affichage (cloche, liste) arrive avec la messagerie, en phase 5."""
    return Notification.objects.create(user=user, type=type, title=title[:140], body=body, url=url[:300])
