"""En-têtes de sécurité ajoutés à toutes les réponses.

CSP : la pile (Alpine.js, scripts JSON des graphiques) impose 'unsafe-inline' et 'unsafe-eval' pour les scripts.
La politique reste utile : aucune ressource externe (scripts, styles, polices, images, XHR) ni intégration par un autre site.
"""
from django.conf import settings

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

# Espaces connectés : jamais mis en cache (navigateur partagé, bouton « retour » après déconnexion).
PRIVATE_PREFIXES = ("/back-office/", "/prestataire/", "/messages/", "/notifications/", "/mon-espace/", "/compte/", "/mes-demandes/", "/favoris/")


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if request.path.startswith(PRIVATE_PREFIXES) and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "private, no-store"
        return response
