"""Filtres et tags utilitaires pour les composants d'interface."""
from urllib.parse import quote

from django import template

register = template.Library()


@register.filter
def star_states(rating):
    """Convertit une note (0-5) en liste de 5 états : full / half / empty."""
    try:
        value = max(0.0, min(5.0, float(rating)))
    except (TypeError, ValueError):
        value = 0.0
    rounded = round(value * 2) / 2
    states = []
    for i in range(1, 6):
        if rounded >= i:
            states.append("full")
        elif rounded >= i - 0.5:
            states.append("half")
        else:
            states.append("empty")
    return states


@register.filter
def initials(name):
    """Initiales (2 lettres max) pour les avatars générés localement."""
    parts = [p for p in str(name or "").replace("-", " ").split() if p]
    if not parts:
        return "K"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@register.simple_tag
def whatsapp_url(number, message=""):
    """Lien click-to-chat wa.me avec message pré-rempli (indicatif +237 ajouté aux numéros locaux)."""
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 9 and digits[0] in "26":
        digits = "237" + digits  # numéro camerounais saisi sans indicatif : wa.me exige le format international
    if not digits:
        return ""
    url = f"https://wa.me/{digits}"
    if message:
        url += f"?text={quote(message)}"
    return url


@register.simple_tag(takes_context=True)
def url_with_params(context, **kwargs):
    """URL courante avec certains paramètres GET remplacés (pagination, tri, filtres)."""
    request = context["request"]
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    query = params.urlencode()
    return f"?{query}" if query else "?"


# (nom d'URL, libellé, icône Lucide, nécessite connexion)
_BOTTOM_NAV = [
    ("core:home", "Accueil", "home", False),
    ("catalog:search", "Recherche", "search", False),
    ("favorites:list", "Favoris", "heart", True),
    ("messaging:inbox", "Messages", "message-circle", True),
    ("accounts:profile", "Mon compte", "user", True),
]


@register.simple_tag(takes_context=True)
def nav_items(context):
    """Entrées de la barre mobile. Une entrée n'apparaît que si sa page existe ; les liens réservés
    aux comptes renvoient les visiteurs vers la connexion, et les prestataires/admins vers leur espace."""
    from django.urls import NoReverseMatch, reverse

    request = context["request"]
    user = request.user
    current = getattr(getattr(request, "resolver_match", None), "view_name", "")
    items = []
    for name, label, icon, needs_login in _BOTTOM_NAV:
        if user.is_authenticated and not user.is_client and name == "favorites:list":
            continue  # les favoris sont une fonction client
        try:
            url = reverse(name)
        except NoReverseMatch:
            continue
        if name == "accounts:profile" and user.is_authenticated and not user.is_client:
            url = user.get_home_url()
        if needs_login and not user.is_authenticated:
            url = f"{reverse('accounts:login')}?next={url}"
        items.append({"url": url, "label": label, "icon": icon, "active": current == name})
    return items


_CLIENT_TABS = [
    ("core:client_home", "Accueil", "layout-dashboard", ("core:client_home",)),
    ("requests_app:list", "Mes demandes", "file-text", ("requests_app:list", "requests_app:detail", "reviews:create", "reviews:edit")),
    ("favorites:list", "Favoris", "heart", ("favorites:list",)),
    ("messaging:inbox", "Messages", "message-circle", ("messaging:inbox", "messaging:thread")),
    ("accounts:profile", "Mon compte", "user", ("accounts:profile", "accounts:password_change", "accounts:delete", "notifications:list")),
]


@register.inclusion_tag("client/_subnav.html", takes_context=True)
def client_subnav(context):
    from django.urls import reverse

    request = context["request"]
    current = getattr(getattr(request, "resolver_match", None), "view_name", "")
    return {"tabs": [
        {"url": reverse(name), "label": label, "icon": icon, "active": current in views}
        for name, label, icon, views in _CLIENT_TABS
    ]}


_REQUEST_BADGES = {
    "SENT": "badge-gray", "VIEWED": "badge-gray", "QUOTED": "badge-yellow", "ACCEPTED": "badge-green",
    "IN_PROGRESS": "badge-orange", "DONE": "badge-green", "CANCELLED": "badge-red", "REFUSED": "badge-red",
}


@register.filter
def request_badge(status):
    """Classe de badge selon le statut d'une demande."""
    return _REQUEST_BADGES.get(status, "badge-gray")


@register.filter
def fcfa(value):
    """Montant en FCFA avec espace insécable pour les milliers : 15000 -> « 15 000 FCFA »."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:,}".replace(",", " ") + " FCFA"


@register.filter
def duration_min(minutes):
    """90 -> « 1 h 30 », 45 -> « 45 min »."""
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        return ""
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours} h {mins:02d}"
    return f"{hours} h" if hours else f"{mins} min"


@register.filter
def get_item(mapping, key):
    """Accès à une valeur de dictionnaire par clé dynamique dans un template."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None
