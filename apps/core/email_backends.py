"""Backends d'envoi d'e-mails par API HTTP.

Utile quand le SMTP sortant est bloqué par l'hébergeur (Render bloque les ports
25/465/587 sur le plan gratuit, par exemple) : l'API Brevo passe par le port
443, qui reste ouvert.

Activer avec :
    EMAIL_BACKEND=apps.core.email_backends.BrevoEmailBackend
    BREVO_API_KEY=xkeysib-...  (clé SMTP & API de https://app.brevo.com)

Brevo offre 300 e-mails/jour gratuitement, sans carte bancaire.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
BREVO_TIMEOUT = 15  # secondes ; ne bloque pas trop longtemps une requête web


def _parse_address(value: str) -> tuple[str, str]:
    """Sépare « Nom <adresse@exemple.cm> » en (nom, adresse). Retourne ("", adresse) si pas de nom."""
    value = (value or "").strip()
    if "<" in value and value.endswith(">"):
        name, _, addr = value.partition("<")
        return name.strip().strip('"'), addr.rstrip(">").strip()
    return "", value


def _recipients(addresses) -> list:
    """Convertit une liste d'adresses Django en destinataires Brevo."""
    out = []
    for value in addresses or []:
        name, email = _parse_address(value)
        recipient = {"email": email}
        if name:
            recipient["name"] = name
        out.append(recipient)
    return out


class BrevoEmailBackend(BaseEmailBackend):
    """Envoie les e-mails via l'API HTTP de Brevo (port 443)."""

    def send_messages(self, email_messages):
        api_key = getattr(settings, "BREVO_API_KEY", "")
        if not api_key:
            raise RuntimeError("BREVO_API_KEY est requis avec le backend e-mail Brevo.")
        num_sent = 0
        for message in email_messages:
            self._send_one(message, api_key)
            num_sent += 1
        return num_sent

    def _send_one(self, message, api_key):
        sender_name, sender_email = _parse_address(message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload = {
            "sender": {"name": sender_name or "Kora", "email": sender_email},
            "to": _recipients(message.to),
            "subject": message.subject,
            "textContent": message.body,
        }
        cc, bcc, reply_to = _recipients(message.cc), _recipients(message.bcc), _recipients(getattr(message, "reply_to", None))
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        if reply_to:
            payload["replyTo"] = reply_to[0]
        for content, mimetype in getattr(message, "alternatives", None) or []:
            if mimetype == "text/html":
                payload["htmlContent"] = content
                break
        request = urllib.request.Request(
            BREVO_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"api-key": api_key, "content-type": "application/json", "accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=BREVO_TIMEOUT) as response:
                body = response.read().decode("utf-8", "replace")
            logger.info("E-mail envoyé via Brevo : %s -> %s (%s)", sender_email, message.to, body[:120])
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            logger.error("Brevo a refusé l'envoi (HTTP %s) : %s", exc.code, detail)
            if not self.fail_silently:
                raise
        except urllib.error.URLError as exc:
            logger.error("API Brevo injoignable : %s", exc.reason)
            if not self.fail_silently:
                raise
