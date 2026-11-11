"""Connexion par e-mail ou par numéro de téléphone."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .models import normalize_phone


class EmailOrPhoneBackend(ModelBackend):
    """`username` peut être une adresse e-mail ou un numéro de téléphone."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        identifier = (username or kwargs.get(User.USERNAME_FIELD) or "").strip()
        if not identifier or password is None:
            return None
        if "@" in identifier:
            lookup = {"email__iexact": identifier}
        else:
            lookup = {"phone": normalize_phone(identifier)}
        try:
            user = User.objects.get(**lookup)
        except User.DoesNotExist:
            # Évite de révéler si le compte existe (temps de calcul constant).
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
