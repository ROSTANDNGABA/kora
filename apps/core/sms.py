"""Envoi de SMS. Le backend « console » affiche le message dans le terminal (développement).

Pour brancher un vrai fournisseur : ajouter une fonction `_send_<nom>` et mettre SMS_BACKEND=<nom>.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _send_console(phone: str, text: str) -> None:
    print(f"\n[SMS -> {phone}] {text}\n")
    logger.info("SMS (console) vers %s", phone)


_BACKENDS = {"console": _send_console}


def send_sms(phone: str, text: str) -> None:
    backend = _BACKENDS.get(settings.SMS_BACKEND)
    if backend is None:
        raise RuntimeError(f"Backend SMS inconnu : {settings.SMS_BACKEND!r}")
    backend(phone, text)
