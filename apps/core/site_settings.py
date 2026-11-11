"""Paramètres généraux modifiables depuis le back-office, avec repli sur les valeurs de settings.py."""
from django.conf import settings
from django.core.cache import cache

CACHE_KEY = "site_settings_v1"


def _load():
    data = cache.get(CACHE_KEY)
    if data is None:
        from .models import SiteSettings

        obj = SiteSettings.objects.first()
        data = {
            "upload_max_mb": obj.upload_max_mb if obj else settings.UPLOAD_MAX_MB,
            "portfolio_max_items": obj.portfolio_max_items if obj else settings.PORTFOLIO_MAX_ITEMS,
            "site_slogan": (obj.site_slogan if obj and obj.site_slogan else ""),
            "support_whatsapp": (obj.support_whatsapp if obj and obj.support_whatsapp else settings.SUPPORT_WHATSAPP),
            "contact_email": obj.contact_email if obj else "",
        }
        cache.set(CACHE_KEY, data, 300)
    return data


def get(key):
    return _load()[key]


def clear_cache():
    cache.delete(CACHE_KEY)


def upload_limit_mb() -> int:
    return get("upload_max_mb")


def upload_limit_bytes() -> int:
    return get("upload_max_mb") * 1024 * 1024


def portfolio_limit() -> int:
    return get("portfolio_max_items")
