"""Journal d'audit : une ligne par action sensible du back-office."""
from apps.core.ratelimit import client_ip

from .models import AuditLog


def log(request, action, entity=None, detail=None):
    """Enregistre qui a fait quoi. `entity` est une instance de modèle (ou None)."""
    return AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        entity_type=entity.__class__.__name__ if entity is not None else "",
        entity_id=str(entity.pk) if entity is not None else "",
        detail=detail or {},
        ip_address=client_ip(request) or None,
    )
