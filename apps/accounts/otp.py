"""Codes de vérification (OTP) par e-mail ou SMS. En dev, ils s'affichent dans la console."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.sms import send_sms

from .models import OTPCode


def _hash(code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def issue_otp(user, channel: str) -> str:
    """Crée un code à 6 chiffres, invalide les précédents et l'envoie. Renvoie le code (utile aux tests)."""
    OTPCode.objects.filter(user=user, channel=channel, is_used=False).update(is_used=True)
    code = f"{secrets.randbelow(1_000_000):06d}"
    OTPCode.objects.create(
        user=user,
        channel=channel,
        code_hash=_hash(code),
        expires_at=timezone.now() + timedelta(minutes=OTPCode.LIFETIME_MINUTES),
    )
    message = _("Votre code de vérification Kora : %(code)s (valable %(n)s minutes).") % {
        "code": code, "n": OTPCode.LIFETIME_MINUTES,
    }
    if channel == OTPCode.Channel.SMS:
        send_sms(user.phone, message)
    else:
        send_mail(_("Votre code de vérification Kora"), message, settings.DEFAULT_FROM_EMAIL, [user.email])
    return code


class OTPResult:
    OK = "ok"
    WRONG = "wrong"
    EXPIRED = "expired"
    LOCKED = "locked"
    MISSING = "missing"


def verify_otp(user, channel: str, code: str) -> str:
    """Vérifie un code. Après 5 essais ratés, le code est invalidé."""
    otp = OTPCode.objects.filter(user=user, channel=channel, is_used=False).first()
    if otp is None:
        return OTPResult.MISSING
    if otp.expires_at < timezone.now():
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return OTPResult.EXPIRED
    if otp.attempts >= OTPCode.MAX_ATTEMPTS:
        return OTPResult.LOCKED
    if not hmac.compare_digest(otp.code_hash, _hash((code or "").strip())):
        otp.attempts += 1
        if otp.attempts >= OTPCode.MAX_ATTEMPTS:
            otp.is_used = True
        otp.save(update_fields=["attempts", "is_used"])
        return OTPResult.LOCKED if otp.is_used else OTPResult.WRONG
    otp.is_used = True
    otp.save(update_fields=["is_used"])
    field = "phone_verified" if channel == OTPCode.Channel.SMS else "email_verified"
    setattr(user, field, True)
    user.save(update_fields=[field])
    return OTPResult.OK
