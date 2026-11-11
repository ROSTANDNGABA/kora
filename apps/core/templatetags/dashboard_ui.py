"""Barres latérales des dashboards prestataire et administrateur."""
from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()

# (nom d'URL, libellé, icône, URL name considérés comme « actifs », clé de badge)
PROVIDER_ITEMS = [
    ("dashboard_provider:home", "Tableau de bord", "layout-dashboard", ("home",), None),
    ("dashboard_provider:profile", "Mon profil", "user-round", ("profile",), None),
    ("dashboard_provider:portfolio", "Portfolio", "images", ("portfolio",), None),
    ("dashboard_provider:services", "Services et tarifs", "tags", ("services", "service_edit", "service_new"), None),
    ("dashboard_provider:availability", "Disponibilités et zones", "calendar-clock", ("availability",), None),
    ("dashboard_provider:requests", "Demandes", "inbox", ("requests", "request_detail"), "new_requests"),
    ("messaging:inbox", "Messages", "message-circle", ("inbox", "thread"), "messages"),
    ("dashboard_provider:reviews", "Avis", "star", ("reviews",), None),
    ("dashboard_provider:stats", "Statistiques", "chart-no-axes-combined", ("stats",), None),
    ("dashboard_provider:verification", "Vérification", "badge-check", ("verification",), None),
    ("notifications:list", "Notifications", "bell", ("list",), "notifications"),
    ("dashboard_provider:settings", "Paramètres", "settings", ("settings", "password_change"), None),
]

# (nom d'URL, libellé, icône, URL names actifs, module de permission, clé de badge)
ADMIN_ITEMS = [
    ("dashboard_admin:home", "Tableau de bord", "layout-dashboard", ("home",), None, None),
    ("dashboard_admin:clients", "Clients", "users", ("clients", "client_detail"), "clients", None),
    ("dashboard_admin:providers", "Prestataires", "hard-hat", ("providers", "provider_detail", "provider_edit"), "providers", "pending_providers"),
    ("dashboard_admin:verifications", "Vérifications", "badge-check", ("verifications",), "providers", "pending_verifications"),
    ("dashboard_admin:categories", "Catégories et champs", "layout-grid", ("categories", "category_edit", "category_new", "category_fields", "field_edit", "field_new", "subcategory_edit", "subcategory_new"), "catalog", None),
    ("dashboard_admin:cities", "Villes et quartiers", "map-pin", ("cities", "city_edit", "city_new", "neighborhood_edit", "neighborhood_new"), "catalog", None),
    ("dashboard_admin:requests", "Demandes", "inbox", ("requests", "request_detail"), "requests", None),
    ("dashboard_admin:reviews", "Avis et modération", "star", ("reviews",), "reviews", None),
    ("dashboard_admin:reports", "Signalements", "flag", ("reports", "report_detail"), "reports", "pending_reports"),
    ("dashboard_admin:content", "Contenu", "newspaper", ("content", "banner_edit", "banner_new", "page_edit", "page_new", "faq_edit", "faq_new"), "content", None),
    ("dashboard_admin:communication", "Communication", "megaphone", ("communication",), "communication", None),
    ("dashboard_admin:team", "Équipe et permissions", "shield-check", ("team", "team_edit", "team_new"), "team", None),
    ("dashboard_admin:audit", "Journal d'audit", "scroll-text", ("audit",), "audit", None),
    ("dashboard_admin:settings", "Paramètres", "settings", ("settings",), "settings", None),
]


def _url(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return ""


def _current(request):
    match = getattr(request, "resolver_match", None)
    return (match.namespace, match.url_name) if match else ("", "")


@register.simple_tag(takes_context=True)
def provider_sidebar(context):
    from apps.dashboard_provider.counts import provider_badges

    request = context["request"]
    badges = provider_badges(request.user)
    namespace, name = _current(request)
    items = []
    for url_name, label, icon, names, badge in PROVIDER_ITEMS:
        url = _url(url_name)
        if not url:
            continue
        ns = url_name.split(":")[0]
        items.append({
            "url": url, "label": label, "icon": icon, "active": namespace == ns and name in names,
            "badge": badges.get(badge, 0) if badge else 0,
        })
    return items


@register.simple_tag(takes_context=True)
def admin_sidebar(context):
    from apps.dashboard_admin.permissions import can_access_module
    from apps.dashboard_admin.counts import admin_badges

    request = context["request"]
    badges = admin_badges()
    namespace, name = _current(request)
    items = []
    for url_name, label, icon, names, module, badge in ADMIN_ITEMS:
        if module and not can_access_module(request.user, module):
            continue
        url = _url(url_name)
        if not url:
            continue
        items.append({
            "url": url, "label": label, "icon": icon, "active": namespace == "dashboard_admin" and name in names,
            "badge": badges.get(badge, 0) if badge else 0,
        })
    return items
