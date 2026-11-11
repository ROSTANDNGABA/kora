"""Limitation de débit simple basée sur le cache Django (compteur à fenêtre fixe)."""
from django.core.cache import cache


def client_ip(request) -> str:
    """IP du client. N'utilise X-Forwarded-For que derrière le proxy configuré (SECURE_PROXY_SSL_HEADER)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded and request.META.get("HTTP_X_FORWARDED_PROTO"):
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _key(scope: str, ident: str) -> str:
    return f"rl:{scope}:{ident}"


def is_limited(scope: str, ident: str, limit: int) -> bool:
    """Vrai si `limit` événements ont déjà été enregistrés dans la fenêtre."""
    return (cache.get(_key(scope, ident)) or 0) >= limit


def hit(scope: str, ident: str, window_seconds: int) -> int:
    """Enregistre un événement et renvoie le total dans la fenêtre."""
    key = _key(scope, ident)
    if cache.add(key, 1, window_seconds):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # clé expirée entre-temps
        cache.set(key, 1, window_seconds)
        return 1


def reset(scope: str, ident: str) -> None:
    cache.delete(_key(scope, ident))
