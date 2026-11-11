"""Création des comptes (logique métier hors des vues)."""
from django.db import transaction

from apps.providers.models import ProviderFieldValue, ProviderProfile

from .models import ClientProfile, User


@transaction.atomic
def register_client(*, email, password, first_name, last_name, phone=None, city=None) -> User:
    user = User.objects.create_user(
        email, password, first_name=first_name, last_name=last_name, phone=phone, role=User.Role.CLIENT
    )
    ClientProfile.objects.create(user=user, city=city)
    return user


@transaction.atomic
def register_provider(
    *, email, password, first_name, last_name, phone, business_name, category, subcategories, city, whatsapp,
    activity_type,
) -> User:
    """Crée un prestataire en statut PENDING : invisible tant qu'un admin ne l'a pas validé."""
    user = User.objects.create_user(
        email, password, first_name=first_name, last_name=last_name, phone=phone, role=User.Role.PROVIDER
    )
    profile = ProviderProfile.objects.create(
        user=user,
        business_name=business_name,
        category=category,
        city=city,
        whatsapp=whatsapp,
        activity_type=activity_type,
        status=ProviderProfile.Status.PENDING,
    )
    profile.subcategories.set(subcategories)
    # Initialise les champs spécifiques du métier (vides) pour que le profil dynamique soit prêt.
    ProviderFieldValue.objects.bulk_create(
        [ProviderFieldValue(provider=profile, field=f) for f in category.fields.filter(is_active=True)]
    )
    return user
