from django import template
from django.middleware.csrf import get_token

from apps.favorites.models import Favorite

register = template.Library()


def favorite_ids(request) -> set:
    """Identifiants des favoris de l'utilisateur, chargés une seule fois par requête."""
    if not hasattr(request, "_favorite_ids"):
        user = request.user
        request._favorite_ids = (
            set(Favorite.objects.filter(user=user).values_list("provider_id", flat=True))
            if user.is_authenticated and user.is_client else set()
        )
    return request._favorite_ids


@register.inclusion_tag("favorites/partials/heart.html", takes_context=True)
def heart_button(context, provider, in_list=False):
    """Cœur des favoris : bouton pour un client, lien de connexion pour un visiteur, rien pour les autres rôles."""
    request = context.get("request")
    pk = getattr(provider, "pk", None)
    show = bool(request and pk)
    user = getattr(request, "user", None)
    is_anonymous = show and not user.is_authenticated
    if show and user.is_authenticated and not user.is_client:
        show = False
    return {
        "show": show, "provider": provider, "anonymous": is_anonymous,
        "is_favorite": show and not is_anonymous and pk in favorite_ids(request),
        "in_list": in_list or bool(context.get("favorites_list")),
        "csrf_token": get_token(request) if show else "", "next": request.get_full_path() if request else "",
    }
